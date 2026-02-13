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

@description('Principal ID to grant Storage Blob Data Contributor role')
param contributorPrincipalId string = ''

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
// Outputs
// ---------------------------------------------------------------------------
output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
