module.exports = {
  title: 'Arrakis Platform Event Catalog',
  tagline: 'Event-driven architecture documentation for the Arrakis platform',
  organizationName: 'Arrakis Platform',
  homepageMarkdownPath: 'docs/index.md',
  editUrl: 'https://github.com/your-org/arrakis-project/edit/main/docs/eventcatalog',
  trailingSlash: true,
  primaryCTA: {
    label: 'Explore Events',
    href: '/events'
  },
  secondaryCTA: {
    label: 'View Services',
    href: '/services'
  },
  footerLinks: [
    { label: 'API Documentation', href: '../build/index.html' },
    { label: 'Architecture Diagrams', href: '../diagrams/README.md' },
    { label: 'GitHub Repository', href: 'https://github.com/your-org/arrakis-project' }
  ],
  users: [
    {
      id: 'platform-team',
      name: 'Platform Engineering Team',
      role: 'Maintainers',
      email: 'platform-team@arrakis.dev',
      slackDirectMessageUrl: 'https://yourcompany.slack.com/team/platform'
    },
    {
      id: 'ml-team',
      name: 'Machine Learning Team',
      role: 'Consumers',
      email: 'ml-team@arrakis.dev'
    }
  ],
  generators: [
    [
      '@eventcatalog/generator-asyncapi',
      {
        services: [
          { path: './event-gateway/asyncapi.yaml', id: 'event-gateway' },
          { path: './ontology-management-service/asyncapi.yaml', id: 'ontology-management-service' }
        ]
      }
    ]
  ]
};
