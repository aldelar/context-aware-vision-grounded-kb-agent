// ---------------------------------------------------------------------------
// main.bicep — Context Aware & Vision Grounded KB Agent
// ---------------------------------------------------------------------------
// Provisions all Azure resources for the context-aware, vision-grounded KB agent:
//   - Monitoring (Log Analytics + Application Insights)
//   - Storage (Staging + Serving accounts)
//   - Azure AI Services (Content Understanding + Embeddings + Agent model)
//   - Azure AI Search (Basic tier, vector + full-text)
//   - Azure Functions (Python, Container App with custom Docker container)
//
// All inter-service auth uses managed identity (no keys/secrets).
// ---------------------------------------------------------------------------

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@minLength(2)
@maxLength(8)
@description('Short project identifier used in all resource names (e.g. "myproj"). Alphanumeric and hyphens only. Max 8 chars to fit Azure Storage 24-char limit.')
param projectName string

@minLength(2)
@maxLength(7)
@description('Name of the environment (e.g., dev, staging, prod). Use "prod" for production.')
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

@description('Published agent endpoint URL (set by scripts/publish-agent.sh)')
param agentEndpoint string = ''

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

// Base name for resources: kebab-case, e.g. '{project}-dev'
var baseName = '${projectName}-${environmentName}'

// Storage account names: lowercase alphanumeric, max 24 chars
// Worst case: st(2) + projectName(8) + staging(7) + env(7) = 24
var stagingStorageName = replace('st${projectName}staging${environmentName}', '-', '')
var servingStorageName = replace('st${projectName}serving${environmentName}', '-', '')
var functionsStorageName = replace('st${projectName}func${environmentName}', '-', '')

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
    deployerPrincipalId: principalId
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
    mistralDeploymentName: aiServices.outputs.mistralDeploymentName
    searchEndpoint: search.outputs.searchEndpoint
    deployerPrincipalId: principalId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    containerAppsEnvId: containerApp.outputs.containerAppsEnvId
  }
}

// ---------------------------------------------------------------------------
// Module: Container Registry
// ---------------------------------------------------------------------------
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Module: Container App (Context Aware & Vision Grounded KB Agent)
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
    agentEndpoint: agentEndpoint
    cosmosEndpoint: cosmosDb.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmosDb.outputs.cosmosDatabaseName
  }
}

// ---------------------------------------------------------------------------
// Module: Foundry Project (child of AI Services)
// ---------------------------------------------------------------------------
module foundryProject 'modules/foundry-project.bicep' = {
  name: 'foundry-project'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    deployerPrincipalId: principalId
    acrLoginServer: containerRegistry.outputs.containerRegistryLoginServer
    acrResourceId: containerRegistry.outputs.containerRegistryId
    appInsightsResourceId: monitoring.outputs.appInsightsId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    webAppPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
  dependsOn: [containerApp]
}

// ---------------------------------------------------------------------------
// Module: Cosmos DB (conversation history)
// ---------------------------------------------------------------------------
module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
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

// AI Services: Cognitive Services User + OpenAI User (Function App + deployer)
module aiServicesRole 'modules/ai-services-role.bicep' = {
  name: 'ai-services-role'
  params: {
    baseName: baseName
    cognitiveServicesUserPrincipalId: functionApp.outputs.functionAppPrincipalId
    deployerPrincipalId: principalId
  }
  dependsOn: [aiServices]
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
    baseName: baseName
    tags: defaultTags
    acrPullPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
}

// ACR: AcrPull (Foundry Project MI used by unpublished hosted agent runtime)
module containerRegistryFoundryRole 'modules/container-registry.bicep' = {
  name: 'container-registry-foundry-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    acrPullPrincipalId: foundryProject.outputs.projectPrincipalId
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
module aiServicesWebAppRole 'modules/ai-services-role.bicep' = {
  name: 'ai-services-webapp-role'
  params: {
    baseName: baseName
    openAIOnlyUserPrincipalId: containerApp.outputs.containerAppPrincipalId
  }
  dependsOn: [aiServices]
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

// Cosmos DB: Data Contributor (Container App MI — read/write conversations)
// Uses a dedicated role module to avoid re-deploying the full cosmos-db module.
module cosmosDbWebAppRole 'modules/cosmos-db-role.bicep' = {
  name: 'cosmos-db-webapp-role'
  params: {
    baseName: baseName
    principalId: containerApp.outputs.containerAppPrincipalId
  }
  dependsOn: [cosmosDb]
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant AI Services managed identity access to dependent services
// The Foundry hosted agent runs under the AI Services account's system-assigned
// identity, so it needs RBAC on search, storage, and AI Services itself.
// ---------------------------------------------------------------------------

// AI Search: Search Index Data Reader (AI Services MI — for search_knowledge_base tool)
module searchAgentRole 'modules/search.bicep' = {
  name: 'search-agent-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexReaderPrincipalId: aiServices.outputs.aiServicesPrincipalId
  }
}

// AI Services: Cognitive Services OpenAI User (AI Services MI — for embedding calls)
module aiServicesAgentRole 'modules/ai-services-role.bicep' = {
  name: 'ai-services-agent-role'
  params: {
    baseName: baseName
    openAIOnlyUserPrincipalId: aiServices.outputs.aiServicesPrincipalId
  }
  dependsOn: [aiServices]
}

// Serving storage: Storage Blob Data Reader (AI Services MI — for image proxy)
module servingStorageAgentRole 'modules/storage.bicep' = {
  name: 'serving-storage-agent-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    readerPrincipalId: aiServices.outputs.aiServicesPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Post-deploy: Grant Foundry Project managed identity access to dependent services
// When testing the unpublished agent in the Foundry UI, the runtime uses the
// project's system-assigned identity (not the AI Services account identity).
// ---------------------------------------------------------------------------

// AI Search: Search Index Data Reader (Foundry Project MI)
module searchFoundryRole 'modules/search.bicep' = {
  name: 'search-foundry-role'
  params: {
    location: location
    baseName: baseName
    tags: defaultTags
    skuName: searchSkuName
    indexReaderPrincipalId: foundryProject.outputs.projectPrincipalId
  }
}

// AI Services: Cognitive Services OpenAI User (Foundry Project MI — for embeddings)
module aiServicesFoundryRole 'modules/ai-services-role.bicep' = {
  name: 'ai-services-foundry-role'
  params: {
    baseName: baseName
    openAIOnlyUserPrincipalId: foundryProject.outputs.projectPrincipalId
  }
  dependsOn: [aiServices]
}

// Serving storage: Storage Blob Data Reader (Foundry Project MI — for images)
module servingStorageFoundryRole 'modules/storage.bicep' = {
  name: 'serving-storage-foundry-role'
  params: {
    location: location
    storageAccountName: servingStorageName
    tags: defaultTags
    containerNames: ['serving']
    readerPrincipalId: foundryProject.outputs.projectPrincipalId
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
output MISTRAL_DEPLOYMENT_NAME string = aiServices.outputs.mistralDeploymentName

// Search
output SEARCH_SERVICE_NAME string = search.outputs.searchName
output SEARCH_ENDPOINT string = search.outputs.searchEndpoint

// Functions (Container App)
output FUNCTION_APP_NAME string = functionApp.outputs.functionAppName
output FUNCTION_APP_URL string = functionApp.outputs.functionAppUrl
output FUNCTIONS_STORAGE_ACCOUNT string = functionApp.outputs.functionsStorageAccountName

// Monitoring
output APPINSIGHTS_NAME string = monitoring.outputs.appInsightsName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString

// Container Registry
output CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.containerRegistryName
output CONTAINER_REGISTRY_LOGIN_SERVER string = containerRegistry.outputs.containerRegistryLoginServer
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.containerRegistryLoginServer

// Web App (Container App)
output WEBAPP_NAME string = containerApp.outputs.containerAppName
output WEBAPP_URL string = containerApp.outputs.containerAppUrl

// Foundry Project (AZURE_AI_* outputs required by AZD agent extension)
output AZURE_AI_PROJECT_ID string = foundryProject.outputs.projectId
output AZURE_AI_PROJECT_ENDPOINT string = foundryProject.outputs.projectEndpoint
output AZURE_AI_PROJECT_NAME string = foundryProject.outputs.projectName
output AZURE_AI_ACCOUNT_NAME string = aiServices.outputs.aiServicesName
output AZURE_OPENAI_ENDPOINT string = replace(aiServices.outputs.aiServicesEndpoint, '.cognitiveservices.azure.com/', '.openai.azure.com/')
output FOUNDRY_PROJECT_NAME string = foundryProject.outputs.projectName
output FOUNDRY_PROJECT_ENDPOINT string = foundryProject.outputs.projectEndpoint

// Cosmos DB
output COSMOS_ENDPOINT string = cosmosDb.outputs.cosmosEndpoint
output COSMOS_DATABASE_NAME string = cosmosDb.outputs.cosmosDatabaseName
