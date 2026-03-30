// ---------------------------------------------------------------------------
// Module: storage.bicep
// Deploys a single Storage Account with specified containers
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Globally unique storage account name (3-24 lowercase alphanumeric)')
param storageAccountName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Container names to create in this account')
param containerNames array = []

@description('Principal ID to grant Storage Blob Data Contributor role (service principal / managed identity)')
param contributorPrincipalId string = ''

@description('Principal ID of the deployer (human user) for blob access')
param deployerPrincipalId string = ''

@description('Principal ID to grant Storage Blob Data Reader role (e.g., Container App MI for read-only access)')
param readerPrincipalId string = ''

// ---------------------------------------------------------------------------
// Storage Account
// ---------------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    // publicNetworkAccess Enabled for local dev purposes to facilitate blob access without VNet/private endpoints, and to allow Azure-managed services (e.g., Functions) to access blobs without firewall restrictions.
    // For production, use VNet + private endpoints and set publicNetworkAccess to 'Disabled' for enhanced security.
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

// ---------------------------------------------------------------------------
// Blob Service + Containers
// ---------------------------------------------------------------------------
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for name in containerNames: {
    parent: blobService
    name: name
    properties: {
      publicAccess: 'None'
    }
  }
]

// ---------------------------------------------------------------------------
// Role Assignment: Storage Blob Data Contributor
// ---------------------------------------------------------------------------
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(contributorPrincipalId)) {
  name: guid(storageAccount.id, contributorPrincipalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    principalId: contributorPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Storage Blob Data Contributor for deployer (User)
// ---------------------------------------------------------------------------
resource deployerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(storageAccount.id, deployerPrincipalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Storage Blob Data Reader (read-only, e.g., Container App MI)
// ---------------------------------------------------------------------------
var storageBlobDataReaderRoleId = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

resource readerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(readerPrincipalId)) {
  name: guid(storageAccount.id, readerPrincipalId, storageBlobDataReaderRoleId)
  scope: storageAccount
  properties: {
    principalId: readerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReaderRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
