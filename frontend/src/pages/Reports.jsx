import React, { useState, useEffect } from 'react';
import { Filter, Calendar, Users, Download, Eye, X } from 'lucide-react';

const Reports = () => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('violation'); // 'violation' or 'proper_disposal'

    // Filters
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [userId, setUserId] = useState(''); // Just ID input for now, ideally a dropdown

    // Modal
    const [selectedImage, setSelectedImage] = useState(null);

    useEffect(() => {
        fetchReports();
    }, [activeTab, startDate, endDate, userId]);

    const fetchReports = async () => {
        setLoading(true);
        try {
            let url = `http://localhost:8000/events/?event_type=${activeTab}&limit=50`;
            if (startDate) url += `&start_date=${startDate}`;
            if (endDate) url += `&end_date=${endDate}`;
            if (userId) url += `&user_id=${userId}`;

            const res = await fetch(url);
            const data = await res.json();
            setEvents(data);
        } catch (e) {
            console.error("Fetch Error:", e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-6 h-full flex flex-col">
            <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 to-blue-500 bg-clip-text text-transparent mb-6">
                Reports & Analytics
            </h1>

            {/* Filters Bar */}
            <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 flex flex-wrap gap-4 items-center">
                <div className="flex bg-gray-900 rounded-lg p-1 border border-gray-700">
                    <button
                        onClick={() => setActiveTab('violation')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'violation' ? 'bg-red-500/20 text-red-400' : 'text-gray-400 hover:text-gray-200'}`}
                    >
                        Violations
                    </button>
                    <button
                        onClick={() => setActiveTab('proper_disposal')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'proper_disposal' ? 'bg-green-500/20 text-green-400' : 'text-gray-400 hover:text-gray-200'}`}
                    >
                        Proper Disposals
                    </button>
                </div>

                <div className="h-6 w-px bg-gray-700 mx-2"></div>

                <div className="flex items-center gap-2 bg-gray-900 px-3 py-2 rounded border border-gray-700">
                    <Calendar size={16} className="text-gray-400" />
                    <input
                        type="date"
                        className="bg-transparent border-none outline-none text-sm text-white w-32"
                        value={startDate} onChange={e => setStartDate(e.target.value)}
                    />
                    <span className="text-gray-600">-</span>
                    <input
                        type="date"
                        className="bg-transparent border-none outline-none text-sm text-white w-32"
                        value={endDate} onChange={e => setEndDate(e.target.value)}
                    />
                </div>

                <div className="flex items-center gap-2 bg-gray-900 px-3 py-2 rounded border border-gray-700">
                    <Users size={16} className="text-gray-400" />
                    <input
                        placeholder="User ID"
                        className="bg-transparent border-none outline-none text-sm text-white w-20"
                        value={userId} onChange={e => setUserId(e.target.value)}
                    />
                </div>

                <button className="ml-auto flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-sm font-medium transition">
                    <Download size={16} /> Export CSV
                </button>
            </div>

            {/* Table */}
            <div className="mt-6 bg-gray-800 rounded-xl border border-gray-700 overflow-hidden flex-1">
                <div className="overflow-x-auto h-full">
                    <table className="w-full text-left">
                        <thead className="bg-gray-900/50 text-gray-400 text-sm uppercase">
                            <tr>
                                <th className="px-6 py-4">ID</th>
                                <th className="px-6 py-4">Timestamp</th>
                                <th className="px-6 py-4">Camera</th>
                                <th className="px-6 py-4">User ID</th>
                                <th className="px-6 py-4">Confidence</th>
                                <th className="px-6 py-4">Evidence</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-700 text-sm">
                            {loading ? (
                                <tr><td colSpan="6" className="p-8 text-center text-gray-500">Loading data...</td></tr>
                            ) : events.length === 0 ? (
                                <tr><td colSpan="6" className="p-8 text-center text-gray-500">No records found matching filters.</td></tr>
                            ) : events.map(ev => (
                                <tr key={ev.id} className="hover:bg-gray-700/30 transition">
                                    <td className="px-6 py-4 text-gray-300">#{ev.id}</td>
                                    <td className="px-6 py-4 text-gray-300">
                                        {new Date(ev.timestamp).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 text-gray-300">Cam {ev.camera_id}</td>
                                    <td className="px-6 py-4 text-gray-300">
                                        {ev.user_id ? (
                                            <span className="text-blue-400">User #{ev.user_id}</span>
                                        ) : (
                                            <span className="text-gray-500 italic">Unknown</span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <div className="w-16 h-1 bg-gray-700 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full ${ev.confidence > 0.8 ? 'bg-green-500' : 'bg-yellow-500'}`}
                                                    style={{ width: `${ev.confidence * 100}%` }}
                                                ></div>
                                            </div>
                                            <span className="text-xs text-gray-400">{Math.round(ev.confidence * 100)}%</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <button
                                            onClick={() => setSelectedImage(ev.image_path || 'placeholder')}
                                            className="text-gray-400 hover:text-white flex items-center gap-2 text-xs bg-gray-700 px-2 py-1 rounded transition"
                                        >
                                            <Eye size={12} /> View
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Image Modal */}
            {selectedImage && (
                <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-gray-900 rounded-2xl border border-gray-700 p-2 max-w-4xl w-full relative">
                        <button
                            onClick={() => setSelectedImage(null)}
                            className="absolute top-4 right-4 bg-gray-800 text-white p-2 rounded-full hover:bg-gray-700 transition"
                        >
                            <X size={20} />
                        </button>
                        <div className="aspect-video bg-black rounded-xl overflow-hidden flex items-center justify-center">
                            {/* In a real app, load actual image from API. For now showing placeholder text/logic */}
                            {selectedImage === 'placeholder' ? (
                                <div className="text-gray-500">Image storage not fully linked yet</div>
                            ) : (
                                <img src={`http://localhost:8000/images/${selectedImage}`} alt="Evidence" className="max-h-full" />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Reports;
