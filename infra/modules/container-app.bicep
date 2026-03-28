// ---------------------------------------------------------------------------
// Module: container-app.bicep
// Deploys Container App for the web app (Next.js + CopilotKit client)
// with Easy Auth (Entra ID, single-tenant) and system-assigned managed identity.
// Requires an existing Container Apps Environment (created by container-apps-env.bicep).
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Container Apps Environment ID (from container-apps-env module)')
param containerAppsEnvId string

@description('ACR login server (e.g., cr{project}dev.azurecr.io)')
param acrLoginServer string

@description('ACR resource ID for role assignment')
param acrResourceId string

@description('Docker image name and tag (e.g., webapp-{project}:latest). Leave empty for initial provisioning.')
param imageName string = ''

// Use a public placeholder image on first deploy (before AZD pushes the real image).
// The placeholder listens on port 80, so provision with that port and switch to 3000 on the real deploy.
var useAcrImage = !empty(imageName)
var containerImage = useAcrImage ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var targetPort = useAcrImage ? 3000 : 80

@description('Serving storage blob endpoint')
param servingBlobEndpoint string

@description('Serving storage container name')
param servingContainerName string = 'serving'

// --- Agent endpoint ---
@description('Agent endpoint URL (Foundry hosted agent or localhost for local dev)')
param agentEndpoint string = ''

// --- Cosmos DB ---
@description('Cosmos DB endpoint')
param cosmosEndpoint string = ''

@description('Cosmos DB database name')
param cosmosDatabaseName string = 'kb-agent'

// --- Easy Auth ---
@description('Entra App Registration client ID for Easy Auth')
param entraClientId string = ''

@description('Entra App Registration client secret for Easy Auth')
@secure()
param entraClientSecret string = ''

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

// ---------------------------------------------------------------------------
// Container App — Context Aware & Vision Grounded KB Agent
// ---------------------------------------------------------------------------
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'webapp-${baseName}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'web-app'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvId
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: !empty(entraClientSecret) ? [
        {
          name: 'microsoft-provider-authentication-secret'
          value: entraClientSecret
        }
      ] : []
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      // Only attach ACR registry config when the deployed image actually lives in ACR.
      // The placeholder MCR image does not need registry auth during provision.
      registries: useAcrImage ? [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: 'webapp'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'SERVING_BLOB_ENDPOINT', value: servingBlobEndpoint }
            { name: 'SERVING_CONTAINER_NAME', value: servingContainerName }
            { name: 'AGENT_ENDPOINT', value: agentEndpoint }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'COSMOS_DATABASE_NAME', value: cosmosDatabaseName }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Easy Auth — Entra ID (Microsoft Identity Platform v2)
// Configured only when entraClientId is provided
// ---------------------------------------------------------------------------
resource authConfig 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (!empty(entraClientId)) {
  parent: containerApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          openIdIssuer: 'https://sts.windows.net/${tenantId}/v2.0'
          clientId: entraClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
        }
        validation: {
          defaultAuthorizationPolicy: {
            allowedApplications: []
          }
          allowedAudiences: [
            'api://${entraClientId}'
          ]
        }
      }
    }
    login: {
      tokenStore: {
        enabled: false
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Role: AcrPull on ACR for container app managed identity
// (Must be in the same module as the Container App to avoid race condition
// between the Container App needing ACR access and ACR role needing the principal ID)
// ---------------------------------------------------------------------------
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResourceId, containerApp.id, acrPullRoleId)
  scope: existingAcr
  properties: {
    principalId: containerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// Reference the existing ACR (for scoping the role assignment)
resource existingAcr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: split(acrResourceId, '/')[8]
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output containerAppId string = containerApp.id
output containerAppName string = containerApp.name
output containerAppPrincipalId string = containerApp.identity.principalId
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
