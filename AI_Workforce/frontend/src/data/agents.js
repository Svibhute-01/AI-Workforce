export const agents = [
  {
    id: 1,
    name: 'Requirement Analyst AI',
    description: 'Analyzes project requirements, extracts requirements and identifies missing or unclear specifications.',
    icon: 'requirement',
    status: 'active',
  },
  {
    id: 2,
    name: 'Project Manager AI',
    description: 'Creates project plans, assigns tasks, tracks progress and manages project timelines.',
    icon: 'project',
    status: 'active',
  },
  {
    id: 3,
    name: 'Developer AI',
    description: 'Generates code, suggests architecture, assists with implementation and creates development documentation.',
    icon: 'developer',
    status: 'active',
  },
  {
    id: 4,
    name: 'QA AI',
    description: 'Generates test cases, identifies possible issues and evaluates software quality.',
    icon: 'qa',
    status: 'active',
  },
]

export const agentActivities = [
  {
    id: 1,
    agent: 'Requirement Analyst AI',
    activity: 'Extracted 25 requirements from project specification',
    timestamp: '2h ago',
  },
  {
    id: 2,
    agent: 'Project Manager AI',
    activity: 'Created Sprint 1 with 18 tasks',
    timestamp: '5h ago',
  },
  {
    id: 3,
    agent: 'Developer AI',
    activity: 'Generated API implementation',
    timestamp: '1d ago',
  },
  {
    id: 4,
    agent: 'QA AI',
    activity: 'Generated 45 test cases',
    timestamp: '2d ago',
  },
]
