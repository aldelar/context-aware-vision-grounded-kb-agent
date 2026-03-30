// ---------------------------------------------------------------------------
// Module: monitoring.bicep
// Deploys Log Analytics workspace + Application Insights
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Principal ID of the deployer (human user) for Log Analytics Reader role on App Insights')
param deployerPrincipalId string = ''

@description('Principal ID of the AI Services managed identity — needs Log Analytics Reader so Foundry can query traces')
param aiServicesPrincipalId string = ''

// ---------------------------------------------------------------------------
// Log Analytics Workspace
// ---------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${baseName}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Application Insights (workspace-based)
// ---------------------------------------------------------------------------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${baseName}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------------------------------------------------------------------------
// Role: Log Analytics Reader — allows the deployer to view traces and
// metrics in the Foundry Control Plane (Operate > Assets).  The Control
// Plane reads Application Insights data and requires this role.
// ---------------------------------------------------------------------------
var logAnalyticsReaderRoleId = '73c42c96-874c-492b-b04d-ab87d138a893'

resource deployerLogAnalyticsReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(appInsights.id, deployerPrincipalId, logAnalyticsReaderRoleId)
  scope: appInsights
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', logAnalyticsReaderRoleId)
  }
}

// ---------------------------------------------------------------------------
// Role: Log Analytics Reader — allows the AI Services managed identity
// (Foundry) to query traces from Application Insights.  Without this,
// the Foundry Operate > Assets > Traces tab shows "No traces found".
// ---------------------------------------------------------------------------
resource aiServicesLogAnalyticsReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiServicesPrincipalId)) {
  name: guid(appInsights.id, aiServicesPrincipalId, logAnalyticsReaderRoleId)
  scope: appInsights
  properties: {
    principalId: aiServicesPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', logAnalyticsReaderRoleId)
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output logAnalyticsWorkspaceId string = logAnalytics.id
output appInsightsId string = appInsights.id
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
output appInsightsName string = appInsights.name
