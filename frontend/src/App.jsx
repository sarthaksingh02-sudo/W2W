import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Register from './pages/Register';
import UsersList from './pages/Users';
import Reports from './pages/Reports';
import { Monitor, FileBarChart, UserCheck, UserPlus } from 'lucide-react';

function App() {
    return (
        <Router>
            <div className="min-h-screen bg-gray-900 text-gray-100 p-6 font-sans">
                <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 to-blue-500 bg-clip-text text-transparent">
                            ECOPE Production
                        </h1>
                    </div>
                    <div className="flex gap-4">
                        <Link to="/" className="flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-800 transition">
                            <Monitor size={18} /> Dashboard
                        </Link>
                        <Link to="/reports" className="flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-800 transition">
                            <FileBarChart size={18} /> Reports
                        </Link>
                        <Link to="/users" className="flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-800 transition">
                            <UserCheck size={18} /> Users
                        </Link>
                        <Link to="/register" className="flex items-center gap-2 px-3 py-2 rounded hover:bg-gray-800 transition">
                            <UserPlus size={18} /> Register
                        </Link>
                        <div className="bg-gray-800 p-2 rounded-lg flex items-center gap-2 ml-4">
                            <div className="w-2 h-2 rounded-full bg-green-500"></div>
                            <span className="text-xs">System Online</span>
                        </div>
                    </div>
                </header>

                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/users" element={<UsersList />} />
                    <Route path="/reports" element={<Reports />} />
                </Routes>
            </div>
        </Router>
    )
}

export default App
