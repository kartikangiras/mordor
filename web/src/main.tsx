import React from 'react'
import ReactDOM from 'react-dom/client'
import { Navigate, createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import MapPage from './routes/MapPage'
import Door from './routes/act/Door'
import Card from './routes/act/Card'
import Queue from './routes/act/Queue'
import Impact from './routes/act/Impact'
import Walk from './routes/act/Walk'
import WalkIntro from './routes/act/WalkIntro'
import SchoolPublic from './routes/SchoolPublic'
import Validation from './routes/Validation'
import Zones from './routes/Zones'
import Records from './routes/Records'
import Front from './routes/Front'
import ErrorBoundary, { RouteError } from './components/ErrorBoundary'
import AppShell from './components/Shell/AppShell'
import MapShell from './components/Shell/MapShell'

const router = createBrowserRouter([
  {
    path: '/', element: <AppShell />, errorElement: <RouteError />,
    children: [
      {
        element: <MapShell />,
        children: [
          { index: true, element: <Front /> },
          { path: 'map', element: <MapPage /> },
          { path: 'story', element: <Navigate to="/story/1" replace /> },
          { path: 'story/:n', element: <MapPage story /> },
          { path: 'act/walk', element: <WalkIntro /> },
          { path: 'act/walk/:n', element: <Walk /> },
        ],
      },
      { path: 'school/:id', element: <SchoolPublic /> },
      { path: 'act', element: <Door /> },
      { path: 'act/card', element: <Card /> },
      { path: 'act/queue', element: <Queue /> },
      { path: 'act/impact', element: <Impact /> },
      { path: 'me', element: <Navigate to="/act" replace /> },
      { path: 'validation', element: <Validation /> },
      { path: 'zones', element: <Zones /> },
      { path: 'records', element: <Records /> },
      { path: 'records/:entity', element: <Records /> },
    ],
  },
], { future: { v7_relativeSplatPath: true, v7_fetcherPersist: true, v7_normalizeFormMethod: true, v7_partialHydration: true, v7_skipActionErrorRevalidation: true } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </ErrorBoundary>
  </React.StrictMode>,
)
