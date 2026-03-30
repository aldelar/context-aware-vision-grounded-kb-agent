// ---------------------------------------------------------------------------
// Module: cosmos-db-role.bicep
// Assigns Cosmos DB Built-in Data Contributor SQL role to a principal.
// Uses existing reference to avoid re-deploying the full cosmos-db module.
// ---------------------------------------------------------------------------

@description('Base name used for resource naming')
param baseName string

@description('Principal ID to grant Cosmos DB Built-in Data Contributor role')
param principalId string

// ---------------------------------------------------------------------------
// Reference existing Cosmos DB account
// ---------------------------------------------------------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: 'cosmos-${baseName}'
}

// ---------------------------------------------------------------------------
// Role Assignment: Cosmos DB Built-in Data Contributor
// ---------------------------------------------------------------------------
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

resource dataContributorAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, principalId, cosmosDataContributorRoleId)
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    scope: cosmosAccount.id
  }
}
