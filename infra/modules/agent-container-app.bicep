// ---------------------------------------------------------------------------
// Module: agent-container-app.bicep
// Deploys the KB Agent as a Container App with external HTTPS ingress with JWT auth
// in the existing Container Apps Environment.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Container Apps Environment ID')
param containerAppsEnvId string

@description('Container Apps Environment default domain (for internal FQDN construction)')
param containerAppsEnvDefaultDomain string

@description('ACR login server (e.g., cr{project}dev.azurecr.io)')
param acrLoginServer string

@description('ACR resource ID for role assignment')
param acrResourceId string

@description('Docker image name and tag. Leave empty for initial provisioning.')
param imageName string = ''

// --- Application settings ---
@description('Azure AI Services endpoint')
param aiServicesEndpoint string

@description('Azure AI Search endpoint')
param searchEndpoint string

@description('Azure AI Search index name')
param searchIndexName string = 'kb-articles'

@description('Serving storage blob endpoint')
param servingBlobEndpoint string

@description('Serving storage container name')
param servingContainerName string = 'serving'

@description('Foundry project endpoint for agent registration')
param projectEndpoint string

@description('Agent model deployment name')
param agentModelDeploymentName string = 'gpt-4.1'

@description('Embedding deployment name')
param embeddingDeploymentName string = 'text-embedding-3-small'

@description('Application Insights connection string')
param applicationInsightsConnectionString string

@description('Cosmos DB endpoint')
param cosmosEndpoint string = ''

@description('Cosmos DB database name')
param cosmosDatabaseName string = 'kb-agent'

// Use a public placeholder image on first deploy (before AZD pushes the real image)
var useAcrImage = !empty(imageName)
var containerImage = useAcrImage ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var appName = 'agent-${baseName}'

// ---------------------------------------------------------------------------
// Container App — KB Agent (internal-only)
// ---------------------------------------------------------------------------
resource agentApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: union(tags, {
    'azd-service-name': 'agent'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8088
        transport: 'auto'
        allowInsecure: false
      }
      // Only configure ACR registry when a real ACR image is used.
      // On initial provisioning (placeholder image), omit ACR to avoid
      // registry validation blocking revision creation before AcrPull role propagates.
      // azd deploy updates the registry config when pushing the real image.
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
          name: 'agent'
          image: containerImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'AI_SERVICES_ENDPOINT', value: aiServicesEndpoint }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'SEARCH_INDEX_NAME', value: searchIndexName }
            { name: 'SERVING_BLOB_ENDPOINT', value: servingBlobEndpoint }
            { name: 'SERVING_CONTAINER_NAME', value: servingContainerName }
            { name: 'PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'AGENT_MODEL_DEPLOYMENT_NAME', value: agentModelDeploymentName }
            { name: 'EMBEDDING_DEPLOYMENT_NAME', value: embeddingDeploymentName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsightsConnectionString }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'COSMOS_DATABASE_NAME', value: cosmosDatabaseName }
            { name: 'OTEL_SERVICE_NAME', value: 'kb-agent' }
            { name: 'REQUIRE_AUTH', value: 'true' }
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
// Role: AcrPull on ACR for agent managed identity
// (Must be in the same module as the Container App to avoid race condition
// between the Container App needing ACR access and ACR role needing the principal ID)
// ---------------------------------------------------------------------------
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResourceId, agentApp.id, acrPullRoleId)
  scope: existingAcr
  properties: {
    principalId: agentApp.identity.principalId
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
output agentEndpoint string = 'http://${appName}.internal.${containerAppsEnvDefaultDomain}'
output agentExternalUrl string = 'https://${agentApp.properties.configuration.ingress.fqdn}'
output agentPrincipalId string = agentApp.identity.principalId
output agentAppName string = agentApp.name
