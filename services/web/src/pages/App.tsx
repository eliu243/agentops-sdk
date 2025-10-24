import React, { useEffect, useState } from 'react'
import { Play, Clock, DollarSign, AlertTriangle, CheckCircle, XCircle, Activity, Sun, Moon, Trash2 } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

type RunSummary = {
  id: string
  project: string
  started_at: number
  ended_at?: number
  status: string
  termination_reason?: string
  total_cost_usd: number
}

type Event = {
  id: number | string
  type: string
  model?: string
  prompt?: string
  response?: string
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  cost_usd?: number
  created_at?: number
  // A2A HTTP fields
  method?: string
  url?: string
  service_name?: string
  request_data?: string
  response_data?: string
  status_code?: number
  duration_ms?: number
  error?: string
}

type RunDetail = RunSummary & { events: Event[] }

const API_URL = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000'

export function App() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const { theme, toggleTheme } = useTheme()

  useEffect(() => {
    fetch(`${API_URL}/v1/runs`).then(r => r.json()).then(setRuns).catch(() => setRuns([]))
  }, [])

  useEffect(() => {
    if (!selected) return
    fetch(`${API_URL}/v1/runs/${selected}`).then(r => r.json()).then(setDetail).catch(() => setDetail(null))
  }, [selected])

  const deleteRun = async (runId: string) => {
    try {
      const response = await fetch(`${API_URL}/v1/runs/${runId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        // Remove from runs list
        setRuns(prev => prev.filter(run => run.id !== runId))
        
        // Clear selection if deleted run was selected
        if (selected === runId) {
          setSelected(null)
          setDetail(null)
        }
        
        setDeleteConfirm(null)
      } else {
        console.error('Failed to delete run')
      }
    } catch (error) {
      console.error('Error deleting run:', error)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <Activity className="w-4 h-4" />
      case 'completed': return <CheckCircle className="w-4 h-4" />
      case 'terminated': return <XCircle className="w-4 h-4" />
      default: return <Clock className="w-4 h-4" />
    }
  }

  const getStatusBadge = (status: string) => {
    const baseClasses = "status-badge"
    switch (status) {
      case 'running': return `${baseClasses} status-running`
      case 'completed': return `${baseClasses} status-completed`
      case 'terminated': return `${baseClasses} status-terminated`
      default: return `${baseClasses} bg-gray-100 text-gray-800`
    }
  }

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 flex">
      {/* Sidebar */}
      <aside className="w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Play className="w-6 h-6 text-primary-600" />
                AgentOps Dashboard
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Monitor your AI agent runs</p>
            </div>
            <button
              onClick={toggleTheme}
              className="theme-toggle"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5 text-yellow-500" />
              ) : (
                <Moon className="w-5 h-5 text-gray-600" />
              )}
            </button>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Recent Runs</h2>
            {runs.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No runs yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {runs.map(run => (
                  <div
                    key={run.id}
                    className={`p-4 rounded-lg border transition-all ${
                      selected === run.id
                        ? 'border-primary-200 bg-primary-50 dark:border-primary-700 dark:bg-primary-900/20'
                        : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm'
                    }`}
                  >
                    <div 
                      className="cursor-pointer"
                      onClick={() => setSelected(run.id)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-gray-900 dark:text-gray-100">{run.project}</span>
                        <div className="flex items-center gap-2">
                          <span className={getStatusBadge(run.status)}>
                            {getStatusIcon(run.status)}
                            <span className="ml-1 capitalize">{run.status}</span>
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setDeleteConfirm(run.id)
                            }}
                            className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/20 transition-colors"
                            title="Delete run"
                          >
                            <Trash2 className="w-4 h-4 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300" />
                          </button>
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                        <span className="font-mono">{run.id.slice(0, 8)}</span>
                        <span className="flex items-center gap-1">
                          <DollarSign className="w-3 h-3" />
                          {run.total_cost_usd.toFixed(6)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {detail ? (
          <RunView run={detail} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Activity className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">Select a run to view details</h3>
              <p className="text-gray-500 dark:text-gray-400">Choose a run from the sidebar to see the trace and metrics</p>
            </div>
          </div>
        )}
      </main>

      {/* Delete Confirmation Dialog */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 dark:bg-red-900/20 rounded-full">
                <Trash2 className="w-6 h-6 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  Delete Run
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  This action cannot be undone
                </p>
              </div>
            </div>
            
            <p className="text-gray-700 dark:text-gray-300 mb-6">
              Are you sure you want to delete this run? All associated events and data will be permanently removed.
            </p>
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteRun(deleteConfirm)}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RunView({ run }: { run: RunDetail }) {
  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString()
  }

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'run_started': return <Play className="w-4 h-4 text-green-600" />
      case 'llm_call': return <Activity className="w-4 h-4 text-blue-600" />
      case 'a2a_http_call': return <DollarSign className="w-4 h-4 text-purple-600" />
      case 'run_terminated': return <AlertTriangle className="w-4 h-4 text-red-600" />
      case 'run_completed': return <CheckCircle className="w-4 h-4 text-green-600" />
      default: return <Clock className="w-4 h-4 text-gray-600" />
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              {getEventIcon('run_started')}
              Run {run.id.slice(0, 8)}
            </h2>
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">{run.project}</span>
              <span className={`status-badge ${
                run.status === 'running' ? 'status-running' :
                run.status === 'completed' ? 'status-completed' :
                'status-terminated'
              }`}>
                {run.status}
              </span>
              {run.termination_reason && (
                <span className="text-red-600 dark:text-red-400 font-medium">{run.termination_reason}</span>
              )}
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-1">
              <DollarSign className="w-6 h-6" />
              {run.total_cost_usd.toFixed(6)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Total Cost</div>
          </div>
        </div>
      </header>

      {/* Events Timeline */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Event Timeline</h3>
          <div className="space-y-4">
            {run.events.map((event, index) => (
              <div key={event.id} className="card p-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 mt-1">
                    {getEventIcon(event.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 capitalize">
                        {event.type.replace('_', ' ')}
                      </h4>
                      <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                        {event.model && (
                          <span className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs font-mono text-gray-800 dark:text-gray-200">
                            {event.model}
                          </span>
                        )}
                        {event.service_name && (
                          <span className="bg-purple-100 dark:bg-purple-900 px-2 py-1 rounded text-xs font-mono text-purple-800 dark:text-purple-200">
                            {event.service_name}
                          </span>
                        )}
                        {event.method && (
                          <span className="bg-blue-100 dark:bg-blue-900 px-2 py-1 rounded text-xs font-mono text-blue-800 dark:text-blue-200">
                            {event.method}
                          </span>
                        )}
                        {event.status_code && (
                          <span className={`px-2 py-1 rounded text-xs font-mono ${
                            event.status_code >= 200 && event.status_code < 300
                              ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                              : event.status_code >= 400
                              ? 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
                              : 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200'
                          }`}>
                            {event.status_code}
                          </span>
                        )}
                        {event.duration_ms && (
                          <span className="text-xs">
                            {event.duration_ms.toFixed(0)}ms
                          </span>
                        )}
                        {event.cost_usd && (
                          <span className="flex items-center gap-1">
                            <DollarSign className="w-3 h-3" />
                            {event.cost_usd.toFixed(6)}
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {event.prompt && (
                      <div className="mb-4">
                        <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Prompt</h5>
                        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
                          <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono">
                            {event.prompt}
                          </pre>
                        </div>
                      </div>
                    )}
                    
                    {event.response && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Response</h5>
                        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
                          <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono">
                            {event.response}
                          </pre>
                        </div>
                      </div>
                    )}
                    
                    {/* A2A HTTP Request/Response Data */}
                    {event.request_data && (
                      <div className="mb-4">
                        <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Request Data</h5>
                        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
                          <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono">
                            {event.request_data}
                          </pre>
                        </div>
                      </div>
                    )}
                    
                    {event.response_data && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Response Data</h5>
                        <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 border border-green-200 dark:border-green-800">
                          <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono">
                            {event.response_data}
                          </pre>
                        </div>
                      </div>
                    )}
                    
                    {event.url && (
                      <div className="mt-3">
                        <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">URL</h5>
                        <div className="text-xs text-gray-600 dark:text-gray-400 font-mono break-all">
                          {event.url}
                        </div>
                      </div>
                    )}
                    
                    {event.error && (
                      <div className="mt-3">
                        <h5 className="text-sm font-medium text-red-700 dark:text-red-300 mb-1">Error</h5>
                        <div className="text-xs text-red-600 dark:text-red-400 font-mono">
                          {event.error}
                        </div>
                      </div>
                    )}
                    
                    {(event.prompt_tokens || event.completion_tokens) && (
                      <div className="mt-3 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                        {event.prompt_tokens && (
                          <span>Prompt: {event.prompt_tokens} tokens</span>
                        )}
                        {event.completion_tokens && (
                          <span>Completion: {event.completion_tokens} tokens</span>
                        )}
                        {event.total_tokens && (
                          <span className="font-medium">Total: {event.total_tokens} tokens</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}


