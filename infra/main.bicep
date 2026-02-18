// ---------------------------------------------------------------------------
// main.bicep — Vision-Grounded Knowledge Agent
// ---------------------------------------------------------------------------
// Provisions all Azure resources for the vision-grounded knowledge agent:
//   - Monitoring (Log Analytics + Application Insights)
//   - Storage (Staging + Serving accounts)
//   - Azure AI Services (Content Understanding + Embeddings + Agent model)
//   - Azure AI Search (Basic tier, vector + full-text)
//   - Azure Functions (Python, Flex Consumption)
//
// All inter-service auth uses managed identity (no keys/secrets).
// ---------------------------------------------------------------------------

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, staging, prod). Used for resource naming.')
param environmentName string

@description('Primary Azure region for all resources')
param location string = 'eastus2'

@description('Tags to apply to all resources')
param tags object = {}

@description('Azure AI Search SKU')
@allowed(['free', 'basic', 'standard'])
param searchSkuName string = 'basic'

@description('Principal ID of the deployer (human user). AZD populates this via AZURE_PRINCIPAL_ID.')
param principalId string = ''

@description('Entra App Registration client ID for web app Easy Auth')
param entraClientId string = ''

@description('Entra App Registration client secret for web app Easy Auth')
@secure()
param entraClientSecret string = ''

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

// Base name for resources: kebab-case, max ~20 chars to stay within limits
var baseName = 'kbidx-${environmentName}'

// Storage account names: lowercase alphanumeric, max 24 chars
var stagingStorageName = replace('stkbidxstaging${environmentName}', '-', '')
var servingStorageName = replace('stkbidxserving${environmentName}', '-', '')
var functionsStorageName = replace('stkbidxfunc${environmentName}', '-', '')

// Merge default tags
var defaultTags = union(tags, {
  'azd-env-name': environmentName
  project: 'kb-ingestion'
})

// ---------------------------------------------------------------------------
// Module: Monitoring
// ---------------------------------------------------------------------------
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: Staging Storage Account
// ---------------------------------------------------------------------------
module stagingStorage 'modules/storage.bicep' = {
  name: 'staging-storage'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
  }
}

// ---------------------------------------------------------------------------
// Module: Serving Storage Account
// ---------------------------------------------------------------------------
module servingStorage 'modules/storage.bicep' = {
  name: 'serving-storage'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
  }
}

// ---------------------------------------------------------------------------
// Module: Azure AI Services (Content Understanding + Models)
// ---------------------------------------------------------------------------
module aiServices 'modules/ai-services.bicep' = {
  name: 'ai-services'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: Azure AI Search
// ---------------------------------------------------------------------------
module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
  }
}

// ---------------------------------------------------------------------------
// Module: Function App
// ---------------------------------------------------------------------------
module functionApp 'modules/function-app.bicep' = {
  name: 'function-app'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    functionsStorageAccountName: functionsStorageName
    stagingBlobEndpoint: stagingStorage.outputs.blobEndpoint
    servingBlobEndpoint: servingStorage.outputs.blobEndpoint
    aiServicesEndpoint: aiServices.outputs.aiServicesEndpoint
    embeddingDeploymentName: aiServices.outputs.embeddingDeploymentName
    agentDeploymentName: aiServices.outputs.agentDeploymentName
    searchEndpoint: search.outputs.searchEndpoint
    deployerPrincipalId: principalId
  }
}

// ---------------------------------------------------------------------------
// Module: Container Registry
// ---------------------------------------------------------------------------
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    location: location
    baseName: environmentName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: Container App (Vision-Grounded Knowledge Agent)
// ---------------------------------------------------------------------------
module containerApp 'modules/container-app.bicep' = {
  name: 'container-app'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    aiServicesEndpoint: aiServices.outputs.aiServicesEndpoint
    embeddingDeploymentName: aiServices.outputs.embeddingDeploymentName
    searchEndpoint: search.outputs.searchEndpoint
    servingBlobEndpoint: servingStorage.outputs.blobEndpoint
    entraClientId: entraClientId
    entraClientSecret: entraClientSecret
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant Function App managed identity access to all services
// ---------------------------------------------------------------------------

// Staging storage: Blob Data Contributor (Function App MI)
module stagingStorageRole 'modules/storage.bicep' = {
  name: 'staging-storage-role'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
    contributorPrincipalId: functionApp.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

// Serving storage: Blob Data Contributor (Function App MI)
module servingStorageRole 'modules/storage.bicep' = {
  name: 'serving-storage-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    contributorPrincipalId: functionApp.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

// AI Services: Cognitive Services User + OpenAI User
module aiServicesRole 'modules/ai-services.bicep' = {
  name: 'ai-services-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    cognitiveServicesUserPrincipalId: functionApp.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

// AI Search: Index Data Contributor + Service Contributor
module searchRole 'modules/search.bicep' = {
  name: 'search-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexContributorPrincipalId: functionApp.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant Container App managed identity access to services
// ---------------------------------------------------------------------------

// ACR: AcrPull (Container App MI)
module containerRegistryRole 'modules/container-registry.bicep' = {
  name: 'container-registry-role'
  params: {
    location: location
    baseName: environmentName
    tags: defaultTags
    acrPullPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// Serving storage: Blob Data Reader (Container App MI — read-only for image proxy)
module servingStorageReaderRole 'modules/storage.bicep' = {
  name: 'serving-storage-reader-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    readerPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// AI Services: Cognitive Services OpenAI User (Container App MI — OpenAI only, no CU)
module aiServicesWebAppRole 'modules/ai-services.bicep' = {
  name: 'ai-services-webapp-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    openAIOnlyUserPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// AI Search: Search Index Data Reader (Container App MI — read-only for querying)
module searchWebAppRole 'modules/search.bicep' = {
  name: 'search-webapp-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexReaderPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Outputs — consumed by AZD and application code
// ---------------------------------------------------------------------------
output AZURE_LOCATION string = location
output RESOURCE_GROUP string = resourceGroup().name

// Storage
output STAGING_STORAGE_ACCOUNT string = stagingStorage.outputs.storageAccountName
output STAGING_BLOB_ENDPOINT string = stagingStorage.outputs.blobEndpoint
output SERVING_STORAGE_ACCOUNT string = servingStorage.outputs.storageAccountName
output SERVING_BLOB_ENDPOINT string = servingStorage.outputs.blobEndpoint

// AI Services
output AI_SERVICES_NAME string = aiServices.outputs.aiServicesName
output AI_SERVICES_ENDPOINT string = aiServices.outputs.aiServicesEndpoint
output EMBEDDING_DEPLOYMENT_NAME string = aiServices.outputs.embeddingDeploymentName
output AGENT_DEPLOYMENT_NAME string = aiServices.outputs.agentDeploymentName
output CU_COMPLETION_DEPLOYMENT_NAME string = aiServices.outputs.cuCompletionDeploymentName

// Search
output SEARCH_SERVICE_NAME string = search.outputs.searchName
output SEARCH_ENDPOINT string = search.outputs.searchEndpoint

// Functions
output FUNCTION_APP_NAME string = functionApp.outputs.functionAppName
output FUNCTION_APP_HOSTNAME string = functionApp.outputs.functionAppDefaultHostname

// Monitoring
output APPINSIGHTS_NAME string = monitoring.outputs.appInsightsName

// Container Registry
output CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.containerRegistryName
output CONTAINER_REGISTRY_LOGIN_SERVER string = containerRegistry.outputs.containerRegistryLoginServer
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.containerRegistryLoginServer

// Web App (Container App)
output WEBAPP_NAME string = containerApp.outputs.containerAppName
output WEBAPP_URL string = containerApp.outputs.containerAppUrl
