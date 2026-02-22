import React, { useState, useEffect } from 'react';
import { Search, User, Shield, Home } from 'lucide-react';

const UsersList = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState('');

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/users/?limit=100');
            const data = await res.json();
            setUsers(data);
        } catch (e) {
            console.error("Fetch Error:", e);
        } finally {
            setLoading(false);
        }
    };

    const filteredUsers = users.filter(u =>
        u.name.toLowerCase().includes(search.toLowerCase()) ||
        (u.flat_number && u.flat_number.toLowerCase().includes(search.toLowerCase()))
    );

    return (
        <div className="p-6 h-full flex flex-col">
            <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 to-blue-500 bg-clip-text text-transparent mb-6">
                Registered Users
            </h1>

            {/* Search Bar */}
            <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 flex items-center gap-4 mb-6">
                <Search size={20} className="text-gray-400" />
                <input
                    placeholder="Search by name or flat number..."
                    className="bg-transparent border-none outline-none text-white flex-1 text-lg"
                    value={search} onChange={e => setSearch(e.target.value)}
                />
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {loading ? (
                    <div className="text-gray-500 col-span-full text-center py-8">Loading users...</div>
                ) : filteredUsers.length === 0 ? (
                    <div className="text-gray-500 col-span-full text-center py-8">No users found.</div>
                ) : filteredUsers.map(user => (
                    <div key={user.id} className="bg-gray-800 border border-gray-700 rounded-xl p-6 hover:border-blue-500/50 transition group relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition">
                            <User size={64} />
                        </div>

                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-xl font-bold">
                                {user.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <h3 className="font-bold text-lg leading-tight">{user.name}</h3>
                                <div className="text-xs text-blue-400">ID: #{user.id}</div>
                            </div>
                        </div>

                        <div className="space-y-2 text-sm text-gray-400">
                            <div className="flex items-center gap-2">
                                <Shield size={14} />
                                <span className="capitalize">{user.role}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Home size={14} />
                                <span>{user.flat_number || "N/A"}</span>
                            </div>
                            <div className="text-xs text-gray-600 mt-4 pt-4 border-t border-gray-700">
                                Registered: {new Date(user.created_at).toLocaleDateString()}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default UsersList;
