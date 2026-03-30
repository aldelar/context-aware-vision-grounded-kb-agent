// ---------------------------------------------------------------------------
// Module: container-apps-env.bicep
// Deploys the Container Apps Environment (Consumption plan) shared by all
// Container Apps (web app, agent, and Azure Functions).
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Log Analytics workspace ID for Container Apps Environment')
param logAnalyticsWorkspaceId string

// ---------------------------------------------------------------------------
// Container Apps Environment (Consumption plan)
// ---------------------------------------------------------------------------
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${baseName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output containerAppsEnvId string = containerAppsEnv.id
output containerAppsEnvName string = containerAppsEnv.name
output containerAppsEnvDefaultDomain string = containerAppsEnv.properties.defaultDomain
