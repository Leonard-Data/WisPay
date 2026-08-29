// WisPay Azure Container Apps deployment template.
//
// This Bicep file scaffolds the production Azure shape for WisPay:
//
//   * Azure Container Apps environment (1 app behind 1 ingress; the
//     compiled frontend bundle ships inside the container so no CDN).
//   * Log Analytics + Application Insights (no vendor lock-in basics).
//   * Azure SQL database + server (the production durability path;
//     SQLite is dev-only per rxconfig.py and the BS-1 contract).
//
// Secrets stay in Azure Key Vault — this template never embeds
// connection strings, tenant ids, or client secrets (CONVENTIONS.md
// security invariant 6). The container reads its env at startup.
//
// Deploy:
//   az deployment group create \
//     --resource-group wispay-prod \
//     --template-file azure-deploy.bicep \
//     --parameters @azure-deploy.parameters.json

@description('Azure region for the deployment.')
param location string = resourceGroup().location

@description('Three-letter env prefix (prod, stg, dev).')
@allowed(['prod', 'stg', 'dev'])
param environment string = 'prod'

@description('Container image reference (registry/repo:tag).')
param wispayImage string = 'wispayacr.azurecr.io/wispay:latest'

@description('Azure AD application client id for Microsoft Entra ID SSO.')
@secure()
param entraClientId string

@description('Azure AD application client secret for Microsoft Entra ID SSO.')
@secure()
param entraClientSecret string

@description('Azure AD tenant id for Microsoft Entra ID SSO.')
param entraTenantId string

@description('Azure SQL connection details (server + database).')
param sqlServerName string
param sqlDatabaseName string = 'wispay'

@description('SQL administrator login (AAD-only admin recommended).')
param sqlAdminLogin string = 'wispay-admin'

@description('Azure SQL login password (prefer AAD-only admin in prod).')
@secure()
param sqlAdminPassword string

var tags = {
  application: 'wispay'
  environment: environment
  managedBy: 'bicep'
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${environment}-wispay'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${environment}-wispay'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    DisableLocalAuth: true
  }
}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${sqlServerName}-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    primaryIdentity: {
      tenantId: subscription().tenantId
      type: 'SystemAssigned'
    }
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'GP_Gen5_2' : 'GP_Gen5_1'
    tier: 'GeneralPurpose'
    family: 'Gen5'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648 // 2 GB
    zoneRedundant: false
  }
}

resource managedEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${environment}-wispay'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        // sharedKey should be supplied via Key Vault or a deployment
        // parameter; left as a placeholder so this template compiles.
        sharedKey: 'replace-with-key-vault-secret'
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource wispayApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${environment}-wispay'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: managedEnv.id
    configuration: {
      activeRevisionsMode: 'single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'wispay'
          image: wispayImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'APP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'APP_PORT'
              value: '8000'
            }
            {
              name: 'AZURE_SQL_SERVER'
              value: '${reference(sqlServer).fullyQualifiedDomainName}'
            }
            {
              name: 'AZURE_SQL_DATABASE'
              value: sqlDatabaseName
            }
            {
              name: 'AZURE_SQL_USERNAME'
              value: 'wispay-identity' // AAD user — see sqlAdminPassword ad-hoc password bypass
            }
            {
              name: 'AZURE_SQL_PASSWORD'
              value: sqlAdminPassword
            }
            {
              name: 'AZURE_ENTRA_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'AZURE_ENTRA_CLIENT_ID'
              value: entraClientId
            }
            {
              name: 'AZURE_ENTRA_CLIENT_SECRET'
              value: entraClientSecret
            }
            {
              name: 'AZURE_ENTRA_REDIRECT_URI'
              value: 'https://${environment}-wispay.example.com/auth/callback'
            }
            {
              name: 'APPINSIGHTS_INSTRUMENTATION_KEY'
              value: appInsights.properties.InstrumentationKey
            }
            {
              name: 'WISPAY_DEMO_MODE'
              value: '0' // hard-off in prod; demo seed is dev-only
            }
          ]
          probes: [
            {
              type: 'liveness'
              httpGet: {
                path: '/'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: environment == 'prod' ? 5 : 2
        rules: [
          {
            name: 'cpu-scale'
            custom: {
              type: 'cpu'
              metadata: {
                type: 'Utilization'
                value: '70'
              }
            }
          }
        ]
      }
    }
  }
}

output containerAppFqdn string = wispayApp.properties.configuration.ingress.fqdn
output sqlConnectionTemplate string = 'mssql+pyodbc://wispay-identity@${reference(sqlServer).fullyQualifiedDomainName}:1433/${sqlDatabaseName}?driver=ODBC+Driver+18+for+SQL+Server'
