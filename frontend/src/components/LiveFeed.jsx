import React, { useEffect, useRef, useState } from 'react';

const LiveFeed = ({ wsUrl }) => {
    // Consumes MJPEG stream from the Python Orchestrator
    const streamUrl = "http://localhost:5000/video_feed";

    return (
        <div className="relative w-full h-full bg-black rounded-lg overflow-hidden border border-gray-700 shadow-xl">
            <div className="absolute top-4 left-4 z-10 bg-red-600 text-white text-xs px-2 py-1 rounded animate-pulse">
                LIVE
            </div>
            <img
                src={streamUrl}
                alt="Live Stream"
                className="w-full h-full object-cover"
                onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.parentElement.querySelector('.error-msg').style.display = 'flex';
                }}
            />
            <div className="error-msg hidden absolute inset-0 flex items-center justify-center text-gray-500 text-center">
                Waiting for Stream... <br />
                (Ensure orchestrator.py is running)
            </div>
        </div>
    );
};

export default LiveFeed;
