import { config } from "./config";
import { UserContext } from "./types";

type EasyAuthClaim = {
  typ?: string;
  val?: string;
};

type EasyAuthPrincipal = {
  auth_typ?: string;
  name_typ?: string;
  role_typ?: string;
  claims?: EasyAuthClaim[];
};

function decodePrincipal(value: string | null): EasyAuthPrincipal | null {
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(Buffer.from(value, "base64").toString("utf8")) as EasyAuthPrincipal;
  } catch {
    return null;
  }
}

function findClaim(principal: EasyAuthPrincipal | null, claimTypes: string[]): string | null {
  if (!principal?.claims) {
    return null;
  }

  const normalizedTypes = new Set(claimTypes.map((claimType) => claimType.toLowerCase()));
  const claim = principal.claims.find((entry) => entry.typ && normalizedTypes.has(entry.typ.toLowerCase()));
  return claim?.val?.trim() || null;
}

function splitHeaderList(value: string | null): string[] {
  if (!value) {
    return [];
  }

  return value.split(",").map((entry) => entry.trim()).filter(Boolean);
}

function resolveGroups(headers: Headers, principal: EasyAuthPrincipal | null): string[] {
  const headerGroups = splitHeaderList(headers.get("x-user-groups") ?? headers.get("x-ms-client-principal-groups"));
  if (headerGroups.length > 0) {
    return headerGroups;
  }

  const principalGroups = principal?.claims
    ?.filter((claim) => claim.typ?.toLowerCase().endsWith("/groups") || claim.typ?.toLowerCase() === "groups")
    .map((claim) => claim.val?.trim())
    .filter((value): value is string => Boolean(value)) ?? [];

  return principalGroups.length > 0 ? principalGroups : config.localUserGroups;
}

export function resolveUserContext(headers: Headers): UserContext {
  const principal = decodePrincipal(headers.get("x-ms-client-principal"));
  const userId =
    headers.get("x-ms-client-principal-id")?.trim() ||
    findClaim(principal, ["oid", "http://schemas.microsoft.com/identity/claims/objectidentifier"]) ||
    config.localUserId;
  const userIdentifier =
    headers.get("x-ms-client-principal-name")?.trim() ||
    findClaim(principal, ["preferred_username", "email", "name", "upn"]) ||
    userId ||
    config.localUserName;

  return {
    groups: resolveGroups(headers, principal),
    userId,
    userIdentifier,
  };
}

export function buildAgentHeaders(headers: Headers): Record<string, string> {
  const user = resolveUserContext(headers);
  const agentHeaders: Record<string, string> = {
    "X-User-Id": user.userId,
    "X-User-Name": user.userIdentifier,
    "X-User-Groups": user.groups.join(","),
  };

  const authorization = headers.get("authorization");
  if (authorization) {
    agentHeaders.Authorization = authorization;
  }

  return agentHeaders;
}