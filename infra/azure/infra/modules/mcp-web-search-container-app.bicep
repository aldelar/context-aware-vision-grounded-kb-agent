// ---------------------------------------------------------------------------
// Module: mcp-web-search-container-app.bicep
// Deploys the MCP Web Search Server as a Container App
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Container Apps Environment ID')
param containerAppsEnvId string

@description('ACR login server')
param acrLoginServer string

@description('ACR resource ID (for AcrPull role assignment)')
param acrResourceId string

@description('Docker image name and tag')
param imageName string = ''

@description('Application environment name (dev or prod)')
param environmentName string

var containerAppName = 'mcp-ws-${baseName}'
var useAcrImage = !empty(imageName)
var envVars = [
  { name: 'ENVIRONMENT', value: environmentName }
  { name: 'MCP_PORT', value: '8089' }
]

resource mcpWebSearch 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'mcp-web-search'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvId
    configuration: {
      ingress: {
        external: false
        targetPort: 8089
        transport: 'auto'
      }
      secrets: []
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
          name: 'mcp-web-search'
          image: useAcrImage ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azurelinux/base/core:3.0'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: envVars
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Role: AcrPull on ACR for mcp-web-search managed identity
// (Must be in the same module as the Container App to avoid race condition
// between the Container App needing ACR access and ACR role needing the principal ID)
// ---------------------------------------------------------------------------
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResourceId, mcpWebSearch.id, acrPullRoleId)
  scope: existingAcr
  properties: {
    principalId: mcpWebSearch.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// Reference the existing ACR (for scoping the role assignment)
resource existingAcr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: split(acrResourceId, '/')[8]
}

@description('Container App FQDN')
output fqdn string = mcpWebSearch.properties.configuration.ingress.fqdn

@description('Container App name')
output name string = mcpWebSearch.name

@description('System-assigned managed identity principal ID')
output principalId string = mcpWebSearch.identity.principalId
