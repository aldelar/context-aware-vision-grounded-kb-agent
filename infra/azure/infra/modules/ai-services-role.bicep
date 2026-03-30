// ---------------------------------------------------------------------------
// Module: ai-services-role.bicep
// Assigns RBAC roles on an existing AI Services account.
// Uses existing reference to avoid re-deploying the account and models.
// ---------------------------------------------------------------------------

@description('Base name used for resource naming')
param baseName string

@description('Principal ID to grant Cognitive Services User + OpenAI User roles (service principal)')
param cognitiveServicesUserPrincipalId string = ''

@description('Principal ID of the deployer (human user) for Cognitive Services access')
param deployerPrincipalId string = ''

@description('Principal ID to grant Cognitive Services OpenAI User role only (e.g., Container App MI)')
param openAIOnlyUserPrincipalId string = ''

// ---------------------------------------------------------------------------
// Reference existing AI Services account
// ---------------------------------------------------------------------------
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: 'ai-${baseName}'
}

// ---------------------------------------------------------------------------
// Role definitions
// ---------------------------------------------------------------------------
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

// ---------------------------------------------------------------------------
// Cognitive Services OpenAI User + Cognitive Services User (service principal)
// ---------------------------------------------------------------------------
resource openAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(cognitiveServicesUserPrincipalId)) {
  name: guid(aiServices.id, cognitiveServicesUserPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: aiServices
  properties: {
    principalId: cognitiveServicesUserPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

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
// Deployer (User principal type)
// ---------------------------------------------------------------------------
resource deployerOpenAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(aiServices.id, deployerPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: aiServices
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalType: 'User'
  }
}

resource deployerCogServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(aiServices.id, deployerPrincipalId, cognitiveServicesUserRoleId)
  scope: aiServices
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------
// Cognitive Services OpenAI User only (e.g., Container App MI)
// ---------------------------------------------------------------------------
resource openAIOnlyUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(openAIOnlyUserPrincipalId)) {
  name: guid(aiServices.id, openAIOnlyUserPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: aiServices
  properties: {
    principalId: openAIOnlyUserPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalType: 'ServicePrincipal'
  }
}
