// ---------------------------------------------------------------------------
// main.bicep — Azure KB Ingestion Pipeline
// ---------------------------------------------------------------------------
// Provisions all Azure resources for the knowledge base ingestion pipeline:
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
    searchEndpoint: search.outputs.searchEndpoint
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant Function App managed identity access to all services
// ---------------------------------------------------------------------------

// Staging storage: Blob Data Contributor
module stagingStorageRole 'modules/storage.bicep' = {
  name: 'staging-storage-role'
  params: {
    location: location
    storageAccountName: stagingStorageName
    tags: defaultTags
    containerNames: ['staging']
    contributorPrincipalId: functionApp.outputs.functionAppPrincipalId
  }
}

// Serving storage: Blob Data Contributor
module servingStorageRole 'modules/storage.bicep' = {
  name: 'serving-storage-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    contributorPrincipalId: functionApp.outputs.functionAppPrincipalId
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

// Search
output SEARCH_SERVICE_NAME string = search.outputs.searchName
output SEARCH_ENDPOINT string = search.outputs.searchEndpoint

// Functions
output FUNCTION_APP_NAME string = functionApp.outputs.functionAppName
output FUNCTION_APP_HOSTNAME string = functionApp.outputs.functionAppDefaultHostname

// Monitoring
output APPINSIGHTS_NAME string = monitoring.outputs.appInsightsName
