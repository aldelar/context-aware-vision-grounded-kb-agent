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

@description('Docker image name and tag')
param imageName string = ''

@description('Environment: dev or prod')
param environment string = 'prod'

@description('Bing Search API key (for prod)')
@secure()
param bingSearchApiKey string = ''

var containerAppName = 'mcp-ws-${baseName}'
var envVars = [
  { name: 'ENVIRONMENT', value: environment }
  { name: 'MCP_PORT', value: '8089' }
  { name: 'BING_SEARCH_API_KEY', secretRef: 'bing-search-api-key' }
]

resource mcpWebSearch 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: tags
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
      secrets: [
        { name: 'bing-search-api-key', value: bingSearchApiKey }
      ]
      registries: !empty(acrLoginServer) ? [
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
          image: !empty(imageName) ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azurelinux/base/core:3.0'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: envVars
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

@description('Container App FQDN')
output fqdn string = mcpWebSearch.properties.configuration.ingress.fqdn

@description('Container App name')
output name string = mcpWebSearch.name

@description('System-assigned managed identity principal ID')
output principalId string = mcpWebSearch.identity.principalId
