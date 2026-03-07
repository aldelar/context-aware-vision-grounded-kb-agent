// ---------------------------------------------------------------------------
// Module: function-app.bicep
// Deploys Azure Functions as a Container App (custom Docker container)
// inside the shared Container Apps Environment.
// Custom container is required for Playwright + Chromium (Mistral converter).
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Storage account name for Functions runtime')
param functionsStorageAccountName string

@description('Staging storage blob endpoint')
param stagingBlobEndpoint string

@description('Serving storage blob endpoint')
param servingBlobEndpoint string

@description('Azure AI Services endpoint')
param aiServicesEndpoint string

@description('Embedding deployment name')
param embeddingDeploymentName string

@description('Agent / completion deployment name')
param agentDeploymentName string

@description('Mistral Document AI deployment name')
param mistralDeploymentName string = 'mistral-document-ai-2512'

@description('Azure AI Search endpoint')
param searchEndpoint string

@description('Azure AI Search index name')
param searchIndexName string = 'kb-articles'

@description('Principal ID of the deployer (human user) for storage access')
param deployerPrincipalId string = ''

@description('ACR login server (e.g., cr{project}dev.azurecr.io)')
param acrLoginServer string

@description('ACR resource ID for role assignment')
param acrResourceId string

@description('Container Apps Environment resource ID')
param containerAppsEnvId string

@description('Docker image name and tag. Leave empty for initial provisioning.')
param imageName string = ''

// Use a public placeholder image on first deploy (before AZD pushes the real image)
var useAcrImage = !empty(imageName)
var containerImage = useAcrImage ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azure-functions/python:4-python3.11'

// ---------------------------------------------------------------------------
// Storage account for Functions runtime
// (Dedicated account, separate from staging/serving)
// ---------------------------------------------------------------------------
resource functionsStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: functionsStorageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

// ---------------------------------------------------------------------------
// Function App as a Container App
// (Runs inside the shared Container Apps Environment)
// ---------------------------------------------------------------------------
resource functionApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'func-${baseName}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'functions'
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
        targetPort: 80
        transport: 'auto'
        allowInsecure: false
      }
      // Always configure ACR registry so azd deploy can push images with managed identity.
      // The AcrPull role is assigned after the Container App is created.
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'functions'
          image: containerImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'AzureWebJobsStorage__accountName', value: functionsStorage.name }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
            { name: 'STAGING_BLOB_ENDPOINT', value: stagingBlobEndpoint }
            { name: 'SERVING_BLOB_ENDPOINT', value: servingBlobEndpoint }
            { name: 'AI_SERVICES_ENDPOINT', value: aiServicesEndpoint }
            { name: 'EMBEDDING_DEPLOYMENT_NAME', value: embeddingDeploymentName }
            { name: 'AGENT_DEPLOYMENT_NAME', value: agentDeploymentName }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'SEARCH_INDEX_NAME', value: searchIndexName }
            { name: 'MISTRAL_DEPLOYMENT_NAME', value: mistralDeploymentName }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 5
        rules: [
          {
            name: 'http-trigger'
            http: {
              metadata: {
                concurrentRequests: '1'
              }
            }
          }
        ]
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Role: AcrPull on ACR for function app managed identity
// (Must be in the same module as the Container App to avoid circular dependency
// between the Container App needing ACR access and ACR role needing the principal ID)
// ---------------------------------------------------------------------------
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResourceId, functionApp.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// Reference the existing ACR (for scoping the role assignment)
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: split(acrResourceId, '/')[8]
}

// ---------------------------------------------------------------------------
// Role: Storage Blob Data Owner on the Functions storage account
// (Required for AzureWebJobsStorage managed identity access)
// ---------------------------------------------------------------------------
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'

resource funcStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionsStorage.id, functionApp.id, storageBlobDataOwnerRoleId)
  scope: functionsStorage
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Role: Storage Blob Data Owner for the deployer (human user)
// ---------------------------------------------------------------------------
resource deployerStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(functionsStorage.id, deployerPrincipalId, storageBlobDataOwnerRoleId)
  scope: functionsStorage
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppFqdn string = functionApp.properties.configuration.ingress.fqdn
output functionAppUrl string = 'https://${functionApp.properties.configuration.ingress.fqdn}'
output functionsStorageAccountName string = functionsStorage.name
