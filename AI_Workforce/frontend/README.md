# AI Workforce - Frontend

A modern, responsive frontend application for the AI Workforce SDLC Automation Platform. This is a React-based web application that provides an intuitive interface for managing software development lifecycle tasks with AI assistance.

## Project Description

AI Workforce is an intelligent platform that helps teams automate and manage their software development processes. The frontend enables users to:

- Manage projects and track progress
- Organize and prioritize tasks
- Collaborate with AI agents for requirements analysis, project management, development, and QA
- Upload and manage project documents
- View analytics and reports
- Integrate with external tools

## Technology Stack

- **React.js 18** - UI framework
- **Vite** - Build tool and development server
- **Tailwind CSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **Lucide React** - Icon library
- **JavaScript (ES6+)** - Programming language

## Folder Structure

```
frontend/
├── public/                 # Static assets
├── src/
│   ├── assets/            # Images, fonts, static files
│   ├── components/
│   │   ├── layout/        # Layout components (Sidebar, Topbar, MainLayout)
│   │   └── common/        # Reusable components (StatusBadge, ProgressBar, Modal, etc.)
│   ├── pages/             # Page components (Dashboard, Projects, Tasks, etc.)
│   ├── data/              # Mock data files
│   ├── services/          # API service (ready for backend integration)
│   ├── hooks/             # Custom React hooks
│   ├── utils/             # Utility functions
│   ├── App.jsx            # Main app component with routing
│   ├── main.jsx           # React entry point
│   └── index.css          # Global styles and Tailwind directives
├── package.json           # Dependencies and scripts
├── vite.config.js         # Vite configuration
├── tailwind.config.js     # Tailwind CSS configuration
├── postcss.config.js      # PostCSS configuration
└── README.md              # Project documentation
```

## Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

4. Preview production build:
   ```bash
   npm run preview
   ```

## Available Routes

- `/login` - Login page
- `/dashboard` - Main dashboard with statistics and project overview
- `/projects` - Projects list and management
- `/projects/:id` - Project details page
- `/tasks` - Tasks management
- `/agents` - AI Agents Hub
- `/chat` - AI Chat interface
- `/documents` - Document management
- `/reports` - Analytics and reports
- `/settings` - User settings and integrations

## Components

### Layout Components
- **Sidebar** - Navigation menu with active state indicators
- **Topbar** - Header with search, notifications, and user profile
- **MainLayout** - Main layout wrapper with sidebar and topbar
- **PrivateRoute** - Route protection for authenticated pages

### Common Components
- **StatCard** - Statistics display card
- **ProgressBar** - Progress visualization
- **StatusBadge** - Status indicator badges
- **Modal** - Reusable modal dialog

## Features

- **Authentication** - Simple localStorage-based authentication
- **Dashboard** - Overview of projects, tasks, and activities
- **Project Management** - Create, view, and manage projects
- **Task Management** - Create tasks with priority and status
- **AI Agents** - Chat interface with different AI agents
- **Document Management** - Upload and manage project documents
- **Analytics** - Reports and performance metrics
- **Settings** - User profile, team management, integrations, security
- **Responsive Design** - Works on desktop, tablet, and mobile

## Mock Data

The application uses mock data located in `src/data/` for demonstration:
- `projects.js` - Sample projects
- `tasks.js` - Sample tasks
- `agents.js` - AI agents and activities
- `documents.js` - Sample documents
- `activities.js` - Recent activities

## API Service

The `src/services/api.js` file contains placeholder functions for future backend integration:
- `apiService.projects.*` - Project CRUD operations
- `apiService.tasks.*` - Task management
- `apiService.agents.*` - Agent interactions
- `apiService.documents.*` - Document operations
- `apiService.reports.*` - Analytics data

## Color Scheme

- **Primary**: #5B2DD8 (Purple)
- **Background**: #f8f7ff (Light Lavender)
- **Card**: #ffffff (White)
- **Text Primary**: #1a1a1a (Dark Gray)
- **Text Secondary**: #666666 (Medium Gray)
- **Border**: #e5e0ff (Light Purple)

## Development Notes

- No TypeScript is used for simplicity
- Redux is not required; React state is sufficient for this application
- The code is structured to be easily understood by final-year students
- No complex abstractions; straightforward React patterns are used
- Mock data can be easily replaced with API calls once the backend is ready

## Future Integration

This frontend is structured to easily connect to a backend API:

1. Replace mock data calls with API calls in component files
2. Update `src/services/api.js` with actual API endpoints
3. Implement proper error handling and loading states
4. Add authentication tokens to API requests
5. Connect to PostgreSQL database through Express backend

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

This project is part of a B.Tech final year project.
