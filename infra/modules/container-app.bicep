// ---------------------------------------------------------------------------
// Module: container-app.bicep
// Deploys Container Apps Environment + Container App for the Vision-Grounded Knowledge Agent
// with Easy Auth (Entra ID, single-tenant) and system-assigned managed identity
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Log Analytics workspace ID for Container Apps Environment')
param logAnalyticsWorkspaceId string

@description('ACR login server (e.g., crkbidxdev.azurecr.io)')
param acrLoginServer string

@description('Docker image name and tag (e.g., webapp-kbidx:latest). Leave empty for initial provisioning.')
param imageName string = ''

// Use a public placeholder image on first deploy (before AZD pushes the real image)
var useAcrImage = !empty(imageName)
var containerImage = useAcrImage ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// --- Application settings ---
@description('Azure AI Services endpoint')
param aiServicesEndpoint string

@description('Agent model deployment name')
param agentModelDeploymentName string = 'gpt-4.1'

@description('Embedding deployment name')
param embeddingDeploymentName string = 'text-embedding-3-small'

@description('Azure AI Search endpoint')
param searchEndpoint string

@description('Azure AI Search index name')
param searchIndexName string = 'kb-articles'

@description('Serving storage blob endpoint')
param servingBlobEndpoint string

@description('Serving storage container name')
param servingContainerName string = 'serving'

// --- Easy Auth ---
@description('Entra App Registration client ID for Easy Auth')
param entraClientId string = ''

@description('Entra App Registration client secret for Easy Auth')
@secure()
param entraClientSecret string = ''

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

// ---------------------------------------------------------------------------
// Container Apps Environment (Consumption plan)
// ---------------------------------------------------------------------------
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${baseName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Container App — Vision-Grounded Knowledge Agent
// ---------------------------------------------------------------------------
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'webapp-${baseName}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'web-app'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: !empty(entraClientSecret) ? [
        {
          name: 'microsoft-provider-authentication-secret'
          value: entraClientSecret
        }
      ] : []
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
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
          name: 'webapp'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AI_SERVICES_ENDPOINT', value: aiServicesEndpoint }
            { name: 'AGENT_MODEL_DEPLOYMENT_NAME', value: agentModelDeploymentName }
            { name: 'EMBEDDING_DEPLOYMENT_NAME', value: embeddingDeploymentName }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'SEARCH_INDEX_NAME', value: searchIndexName }
            { name: 'SERVING_BLOB_ENDPOINT', value: servingBlobEndpoint }
            { name: 'SERVING_CONTAINER_NAME', value: servingContainerName }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Easy Auth — Entra ID (Microsoft Identity Platform v2)
// Configured only when entraClientId is provided
// ---------------------------------------------------------------------------
resource authConfig 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (!empty(entraClientId)) {
  parent: containerApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          openIdIssuer: 'https://sts.windows.net/${tenantId}/v2.0'
          clientId: entraClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
        }
        validation: {
          defaultAuthorizationPolicy: {
            allowedApplications: []
          }
          allowedAudiences: [
            'api://${entraClientId}'
          ]
        }
      }
    }
    login: {
      tokenStore: {
        enabled: false
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output containerAppId string = containerApp.id
output containerAppName string = containerApp.name
output containerAppPrincipalId string = containerApp.identity.principalId
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppsEnvId string = containerAppsEnv.id
output containerAppsEnvName string = containerAppsEnv.name
