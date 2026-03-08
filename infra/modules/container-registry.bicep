// ---------------------------------------------------------------------------
// Module: container-registry.bicep
// Deploys Azure Container Registry (Basic) for hosting web app Docker images
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Principal ID to grant AcrPull role (Container App managed identity)')
param acrPullPrincipalId string = ''

// ---------------------------------------------------------------------------
// Container Registry
// ---------------------------------------------------------------------------
var acrName = replace('cr${baseName}', '-', '')

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: AcrPull (for Container App managed identity)
// ---------------------------------------------------------------------------
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(acrPullPrincipalId)) {
  name: guid(containerRegistry.id, acrPullPrincipalId, acrPullRoleId)
  scope: containerRegistry
  properties: {
    principalId: acrPullPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output containerRegistryId string = containerRegistry.id
output containerRegistryName string = containerRegistry.name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
