import React, { useState, useEffect } from 'react';
import { Bell, Activity, Users, Trash2, Camera, Eye, X, CheckCircle, AlertTriangle } from 'lucide-react';
import LiveFeed from '../components/LiveFeed';

const Dashboard = () => {
    const [stats, setStats] = useState({
        total_users: 0,
        today_violations: 0,
        today_proper: 0
    });

    const [violations, setViolations] = useState([]);
    const [disposals, setDisposals] = useState([]);
    const [users, setUsers] = useState([]);
    const [selectedImage, setSelectedImage] = useState(null);

    // Initial Fetch
    useEffect(() => {
        fetchInitialData();
    }, []);

    const fetchInitialData = async () => {
        try {
            // Fetch Stats
            const usersRes = await fetch('http://localhost:8000/users/');
            const usersData = await usersRes.json();
            setUsers(usersData);

            const violRes = await fetch('http://localhost:8000/events/?event_type=violation&limit=10');
            const violData = await violRes.json();
            setViolations(violData);

            const dispRes = await fetch('http://localhost:8000/events/?event_type=proper_disposal&limit=10');
            const dispData = await dispRes.json();
            setDisposals(dispData);

            setStats({
                total_users: usersData.length,
                today_violations: violData.length, // Simplified, ideally separate stats endpoint
                today_proper: dispData.length
            });
        } catch (e) {
            console.error("Data Fetch Error:", e);
        }
    };

    // WebSocket Listener
    useEffect(() => {
        const ws = new WebSocket("ws://localhost:8000/ws");
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log("WebSocket Event:", data);

                const newEvent = {
                    id: Date.now(),
                    timestamp: data.timestamp || new Date().toISOString(),
                    event_type: data.type,
                    camera_id: data.camera || '1',
                    user_id: data.user || null,
                    confidence: data.confidence || 0.95,
                    image_path: data.image_path,
                    user_name: data.user // Assuming backend sends name if known
                };

                if (data.type === 'violation') {
                    setViolations(prev => [newEvent, ...prev].slice(0, 10));
                    setStats(prev => ({ ...prev, today_violations: prev.today_violations + 1 }));
                } else if (data.type === 'proper_disposal') {
                    setDisposals(prev => [newEvent, ...prev].slice(0, 10));
                    setStats(prev => ({ ...prev, today_proper: prev.today_proper + 1 }));
                }
            } catch (e) {
                console.error("WS Parse Error:", e);
            }
        };
        return () => ws.close();
    }, []);

    return (
        <div className="flex flex-col gap-6">
            {/* Top Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 shadow-xl">
                    <div className="flex justify-between items-center mb-4">
                        <span className="text-gray-400 font-medium">Registered Users</span>
                        <Users className="text-blue-400" size={24} />
                    </div>
                    <div className="text-4xl font-bold">{stats.total_users}</div>
                    <div className="text-sm text-gray-500 mt-2">Active in system</div>
                </div>
                <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 shadow-xl border-l-4 border-l-red-500">
                    <div className="flex justify-between items-center mb-4">
                        <span className="text-gray-400 font-medium">Daily Violations</span>
                        <AlertTriangle className="text-red-400" size={24} />
                    </div>
                    <div className="text-4xl font-bold text-red-100">{stats.today_violations}</div>
                    <div className="text-sm text-red-400/60 mt-2">Requires attention</div>
                </div>
                <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 shadow-xl border-l-4 border-l-green-500">
                    <div className="flex justify-between items-center mb-4">
                        <span className="text-gray-400 font-medium">Proper Disposals</span>
                        <CheckCircle className="text-green-400" size={24} />
                    </div>
                    <div className="text-4xl font-bold text-green-100">{stats.today_proper}</div>
                    <div className="text-sm text-green-400/60 mt-2">Clean environment</div>
                </div>
            </div>

            {/* Main Interactive Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Live Feed Viewer */}
                <div className="lg:col-span-2 bg-gray-950 rounded-2xl border border-gray-800 overflow-hidden relative shadow-2xl min-h-[500px]">
                    <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-black/50 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/10">
                        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                        <span className="text-xs font-bold uppercase tracking-wider text-white">Live Camden-01</span>
                    </div>
                    <LiveFeed />
                </div>

                {/* Registered Users List */}
                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6 shadow-xl flex flex-col">
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Users size={18} /> Recent Residents
                    </h3>
                    <div className="space-y-4 overflow-y-auto max-h-[400px] pr-2 custom-scrollbar">
                        {users.map(user => (
                            <div key={user.id} className="flex items-center gap-3 p-3 bg-gray-900/50 rounded-xl border border-gray-700/50">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-lg">
                                    {user.name[0]}
                                </div>
                                <div className="flex-1">
                                    <div className="text-sm font-semibold">{user.name}</div>
                                    <div className="text-xs text-gray-500">Flat {user.flat_number || 'N/A'}</div>
                                </div>
                                <div className="text-[10px] text-gray-600">ID #{user.id}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Tables Row */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {/* Violations Table */}
                <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden shadow-xl">
                    <div className="p-4 bg-red-500/10 border-b border-gray-700 flex justify-between items-center">
                        <h3 className="font-bold text-red-400 flex items-center gap-2">
                            <Activity size={18} /> Active Violations
                        </h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-gray-900/50 text-gray-400 uppercase text-[10px] tracking-widest">
                                <tr>
                                    <th className="px-4 py-3">Resident</th>
                                    <th className="px-4 py-3">Time</th>
                                    <th className="px-4 py-3">Confidence</th>
                                    <th className="px-4 py-3 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-700/50">
                                {violations.map(v => (
                                    <tr key={v.id} className="hover:bg-gray-700/20 transition">
                                        <td className="px-4 py-3">
                                            <div className="font-medium text-gray-200">{v.user_name || 'Unknown'}</div>
                                            <div className="text-[10px] text-gray-500">Cam {v.camera_id}</div>
                                        </td>
                                        <td className="px-4 py-3 text-gray-400">
                                            {new Date(v.timestamp).toLocaleTimeString()}
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${v.confidence > 0.8 ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-500'}`}>
                                                {Math.round(v.confidence * 100)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => setSelectedImage(v.image_path)}
                                                className="p-1.5 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition"
                                            >
                                                <Eye size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Proper Disposals Table */}
                <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden shadow-xl">
                    <div className="p-4 bg-green-500/10 border-b border-gray-700 flex justify-between items-center">
                        <h3 className="font-bold text-green-400 flex items-center gap-2">
                            <CheckCircle size={18} /> Proper Disposals
                        </h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-gray-900/50 text-gray-400 uppercase text-[10px] tracking-widest">
                                <tr>
                                    <th className="px-4 py-3">Resident</th>
                                    <th className="px-4 py-3">Time</th>
                                    <th className="px-4 py-3">Camera</th>
                                    <th className="px-4 py-3 text-right">Evidence</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-700/50">
                                {disposals.map(d => (
                                    <tr key={d.id} className="hover:bg-gray-700/20 transition">
                                        <td className="px-4 py-3 font-medium text-gray-200">{d.user_name || 'Unknown'}</td>
                                        <td className="px-4 py-3 text-gray-400">
                                            {new Date(d.timestamp).toLocaleTimeString()}
                                        </td>
                                        <td className="px-4 py-3 text-gray-500">Cam {d.camera_id}</td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => setSelectedImage(d.image_path)}
                                                className="text-gray-400 hover:text-green-400 transition"
                                            >
                                                <Camera size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Evidence Image Viewer Modal */}
            {selectedImage && (
                <div className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-xl flex items-center justify-center p-4">
                    <div className="bg-gray-900 rounded-3xl border border-white/10 p-2 max-w-5xl w-full relative shadow-[0_0_50px_rgba(0,0,0,0.5)]">
                        <button
                            onClick={() => setSelectedImage(null)}
                            className="absolute top-4 right-4 bg-gray-800/80 text-white p-2 rounded-full hover:bg-red-500 transition z-10"
                        >
                            <X size={20} />
                        </button>
                        <div className="aspect-video bg-black rounded-2xl overflow-hidden flex items-center justify-center ring-1 ring-white/5">
                            <img
                                src={`http://localhost:8000/images/${selectedImage}`}
                                alt="Evidence"
                                className="max-h-full transition-transform duration-500 hover:scale-105"
                                onError={(e) => {
                                    e.target.src = 'https://via.placeholder.com/800x450?text=Evidence+Image+Not+Found';
                                }}
                            />
                        </div>
                        <div className="p-4 text-center">
                            <p className="text-gray-400 text-sm italic">Capture ID: {selectedImage}</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
