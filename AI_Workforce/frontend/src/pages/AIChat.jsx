import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { agents } from '../data/agents'

function AIChat() {
  const [selectedAgent, setSelectedAgent] = useState(1)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const getMockResponse = (userMessage, agentName) => {
    const responses = {
      'Requirement Analyst AI': [
        'I have analyzed the requirements. Here are the key findings: The system requires user authentication, payment processing, and real-time notifications.',
        'I have identified 5 missing requirements that need clarification from the stakeholders.',
        'The requirements are well-defined for the core features. I recommend adding API rate limiting specifications.',
      ],
      'Project Manager AI': [
        'I have created Sprint 1 with 18 tasks. The estimated completion date is June 15, 2025.',
        'Current project status: 75% complete. We are on track to meet the deadline.',
        'I recommend reallocating 2 team members to the QA phase for faster testing.',
      ],
      'Developer AI': [
        'I have generated the database schema for the project. The schema includes 12 tables with proper indexing.',
        'Here is the API implementation: The endpoints follow RESTful conventions with proper error handling.',
        'I suggest implementing caching for frequently accessed data to improve performance.',
      ],
      'QA AI': [
        'I have generated 45 test cases covering all major features. The estimated testing time is 5 days.',
        'I found 3 critical bugs and 12 minor issues that need to be addressed before release.',
        'The code coverage is 87%. I recommend improving coverage for edge cases.',
      ],
    }

    const agentResponses = responses[agentName] || ['I am ready to help you with this project.']
    return agentResponses[Math.floor(Math.random() * agentResponses.length)]
  }

  const handleSendMessage = () => {
    if (!input.trim()) return

    const userMessage = {
      id: Date.now(),
      text: input,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages([...messages, userMessage])
    setInput('')
    setIsLoading(true)

    setTimeout(() => {
      const agentName = agents.find(a => a.id === selectedAgent)?.name || 'AI Agent'
      const responseText = getMockResponse(input, agentName)

      const agentMessage = {
        id: Date.now() + 1,
        text: responseText,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      }

      setMessages(prev => [...prev, agentMessage])
      setIsLoading(false)
    }, 1000)
  }

  const currentAgent = agents.find(a => a.id === selectedAgent)

  return (
    <div className="flex h-[calc(100vh-120px)] gap-6">
      <div className="w-64 bg-white rounded-lg border border-border-light flex flex-col overflow-hidden">
        <div className="p-4 border-b border-border-light">
          <h3 className="font-bold text-text-primary text-sm">Conversation History</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <div className="p-3 bg-primary-light text-primary rounded-lg text-sm font-medium cursor-pointer">
            Chat with Developer AI
          </div>
        </div>
      </div>

      <div className="flex-1 card flex flex-col">
        <div className="p-6 border-b border-border-light flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-text-primary">AI Chat</h2>
            <p className="text-sm text-text-secondary">Collaborate with AI agents</p>
          </div>
          <select
            value={selectedAgent}
            onChange={(e) => {
              setSelectedAgent(parseInt(e.target.value))
              setMessages([])
            }}
            className="input-field"
          >
            {agents.map(agent => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-center">
              <div>
                <p className="text-text-secondary mb-2">Start a conversation with {currentAgent?.name}</p>
                <p className="text-sm text-text-secondary">{currentAgent?.description}</p>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs p-3 rounded-lg ${
                  message.sender === 'user'
                    ? 'bg-primary text-white rounded-br-none'
                    : 'bg-white border border-border-light text-text-primary rounded-bl-none'
                }`}
              >
                <p className="text-sm">{message.text}</p>
                <p className={`text-xs mt-1 ${message.sender === 'user' ? 'text-purple-100' : 'text-text-secondary'}`}>
                  {message.timestamp}
                </p>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white border border-border-light p-3 rounded-lg rounded-bl-none">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="p-6 border-t border-border-light bg-white">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Type your message..."
              className="input-field flex-1"
            />
            <button
              onClick={handleSendMessage}
              disabled={isLoading}
              className="btn-primary flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AIChat
