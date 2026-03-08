// ---------------------------------------------------------------------------
// Module: foundry-project.bicep
// Deploys a Foundry project as a child of the existing AIServices resource.
// The project inherits all model deployments from the parent — no
// duplication needed.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Principal ID of the deployer (human user) for Azure AI Developer role')
param deployerPrincipalId string = ''

@description('ACR login server (e.g. cr{project}dev.azurecr.io) for the container registry connection')
param acrLoginServer string = ''

@description('ACR resource ID for the container registry connection')
param acrResourceId string = ''

@description('Application Insights resource ID for tracing connection')
param appInsightsResourceId string = ''

@description('Application Insights connection string (used as credential key)')
@secure()
param appInsightsConnectionString string = ''

@description('Principal ID of the web app Container App MI — gets Azure AI User role to call the agent Responses API')
param webAppPrincipalId string = ''

// ---------------------------------------------------------------------------
// Foundry Project (child of AIServices)
// ---------------------------------------------------------------------------
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: 'ai-${baseName}'
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServicesAccount
  name: 'proj-${baseName}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'agent'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'KB Agent Foundry project'
    displayName: 'KB Agent (proj-${baseName})'
  }
}

// ---------------------------------------------------------------------------
// Role: Azure AI User — allows the project MI to interact with the
// Foundry Agent Service runtime on the parent AI account.
// Without this the hosted-agent container startup hangs forever.
// ---------------------------------------------------------------------------
var azureAIUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource projectAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServicesAccount.id, project.name, azureAIUserRoleId)
  scope: aiServicesAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAIUserRoleId)
  }
}

// ---------------------------------------------------------------------------
// Role: Azure AI User — allows the web app to call the published agent
// Responses API endpoint (/applications/{app}/protocols/openai).
// Without this the web app gets 403 ForbiddenError on agent calls.
// ---------------------------------------------------------------------------
resource webAppAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(webAppPrincipalId)) {
  name: guid(aiServicesAccount.id, webAppPrincipalId, azureAIUserRoleId)
  scope: aiServicesAccount
  properties: {
    principalId: webAppPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAIUserRoleId)
  }
}

// ---------------------------------------------------------------------------
// Role: Azure AI Developer — allows the deployer to manage agents.
// ---------------------------------------------------------------------------
var azureAIDeveloperRoleId = '64702f94-c441-49e6-a78b-ef80e0188fee'

resource deployerAIDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(resourceGroup().id, deployerPrincipalId, azureAIDeveloperRoleId)
  scope: resourceGroup()
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAIDeveloperRoleId)
  }
}

// ---------------------------------------------------------------------------
// Role: Reader — allows the deployer to see agents in the Foundry
// Control Plane (Operate > Assets).  The Control Plane discovery queries
// ARM and requires a standard Reader/Contributor/Owner role on the
// resource group — AI-specific roles alone are not sufficient.
// Ref: https://learn.microsoft.com/azure/ai-foundry/control-plane/how-to-manage-agents
// See also: Log Analytics Reader on App Insights (deployed in monitoring.bicep)
// ---------------------------------------------------------------------------
var readerRoleId = 'acdd72a7-3385-48ef-bd42-f606fba81ae7'

resource deployerReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(resourceGroup().id, deployerPrincipalId, readerRoleId)
  scope: resourceGroup()
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', readerRoleId)
  }
}

// ---------------------------------------------------------------------------
// Connection: Container Registry — tells the Foundry Agent Service
// how to pull the hosted-agent container image from our ACR.
// Without this connection the "Starting agent container" phase hangs.
// ---------------------------------------------------------------------------
resource acrConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(acrLoginServer)) {
  parent: project
  name: 'acr-connection'
  properties: {
    category: 'ContainerRegistry'
    target: acrLoginServer
    authType: 'ManagedIdentity'
    isSharedToAll: true
    credentials: {
      clientId: project.identity.principalId
      resourceId: acrResourceId
    }
    metadata: {
      ResourceId: acrResourceId
    }
  }
}

// ---------------------------------------------------------------------------
// Connection: Application Insights — enables the Foundry portal Traces tab
// and allows the agent runtime to export telemetry to App Insights.
// Without this the portal shows "Create or connect an App Insights resource".
// Per foundry-samples: category='AppInsights', key=ConnectionString, account-level.
// ---------------------------------------------------------------------------
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = if (!empty(appInsightsResourceId)) {
  parent: aiServicesAccount
  name: 'appinsights-connection'
  properties: {
    category: 'AppInsights'
    target: appInsightsResourceId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: appInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsightsResourceId
    }
  }
}

// ---------------------------------------------------------------------------
// Capability Host: Account-level (managed ACA environment for hosted agents)
// Created during `azd provision` so the managed environment has time to
// fully spin up before agent deployment.  Without this the deploy hangs
// at "Starting agent container" with a 15-minute timeout.
// ---------------------------------------------------------------------------
resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-10-01-preview' = {
  parent: aiServicesAccount
  name: 'agents'
  properties: {
    capabilityHostKind: 'Agents'
    enablePublicHostingEnvironment: true
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output projectId string = project.id
output projectName string = project.name
output projectEndpoint string = project.properties.endpoints['AI Foundry API']
output projectPrincipalId string = project.identity.principalId
