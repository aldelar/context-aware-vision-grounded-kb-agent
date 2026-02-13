// ---------------------------------------------------------------------------
// Module: ai-services.bicep
// Deploys Azure AI Services (Foundry) account with model deployments
// Used for: Content Understanding, Embeddings, and Agent (GPT-5-mini)
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Principal ID to grant Cognitive Services roles')
param cognitiveServicesUserPrincipalId string = ''

// ---------------------------------------------------------------------------
// Azure AI Services Account (Foundry resource)
// Provides: Content Understanding, OpenAI model hosting
// ---------------------------------------------------------------------------
resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'ai-${baseName}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'ai-${baseName}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: text-embedding-3-small (for fn-index)
// ---------------------------------------------------------------------------
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'text-embedding-3-small'
  sku: {
    name: 'GlobalStandard'
    capacity: 120 // 120K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: gpt-5-mini (for future agent)
// ---------------------------------------------------------------------------
resource agentDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'gpt-5-mini'
  dependsOn: [embeddingDeployment] // Serial deployment to avoid conflicts
  sku: {
    name: 'GlobalStandard'
    capacity: 30 // 30K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Cognitive Services OpenAI User
// ---------------------------------------------------------------------------
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(cognitiveServicesUserPrincipalId)) {
  name: guid(aiServices.id, cognitiveServicesUserPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: aiServices
  properties: {
    principalId: cognitiveServicesUserPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Cognitive Services User (for Content Understanding)
// ---------------------------------------------------------------------------
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource cogServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(cognitiveServicesUserPrincipalId)) {
  name: guid(aiServices.id, cognitiveServicesUserPrincipalId, cognitiveServicesUserRoleId)
  scope: aiServices
  properties: {
    principalId: cognitiveServicesUserPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output aiServicesId string = aiServices.id
output aiServicesName string = aiServices.name
output aiServicesEndpoint string = aiServices.properties.endpoint
output embeddingDeploymentName string = embeddingDeployment.name
output agentDeploymentName string = agentDeployment.name
