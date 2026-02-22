import React, { useState, useRef, useEffect } from 'react';

const Register = () => {
    const [name, setName] = useState('');
    const [role, setRole] = useState('resident');
    const [flatNumber, setFlatNumber] = useState('');
    const [capturing, setCapturing] = useState(false);
    const [images, setImages] = useState([]);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('');

    const videoRef = useRef(null);
    const canvasRef = useRef(null);

    useEffect(() => {
        // Start Camera
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(stream => {
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
            })
            .catch(err => {
                console.error("Camera Error:", err);
                setStatus("Camera access denied.");
            });

        return () => {
            // Stop Camera on unmount
            if (videoRef.current && videoRef.current.srcObject) {
                videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            }
        }
    }, []);

    const startCapture = () => {
        if (!name) {
            alert("Please enter a name first.");
            return;
        }
        setCapturing(true);
        setImages([]);
        setProgress(0);
        setStatus("Capturing face samples... Look at the camera.");

        let count = 0;
        const interval = setInterval(() => {
            if (count >= 20) {
                clearInterval(interval);
                setCapturing(false);
                setStatus("Capture complete. Submitting...");
                submitData();
                return;
            }

            captureFrame();
            count++;
            setProgress(count);
        }, 200); // Capture every 200ms
    };

    const captureFrame = () => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (video && canvas) {
            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            canvas.toBlob(blob => {
                setImages(prev => [...prev, blob]);
            }, 'image/jpeg');
        }
    };

    const submitData = async () => {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('role', role);
        formData.append('flat_number', flatNumber);

        // We need to wait for state update in a real app, but here we read from current batch?
        // Actually state updates are async. Better to use a reliable way.
        // For simplicity, we trust the count logic or use a ref for images if needed.
        // BUT 'images' state might not be fully updated yet due to closure.
        // Let's rely on the fact that by the time submitData is called, previous blobs are mostly there 
        // or we pass them.
        // fix: define images array outside.
    };

    // Refined Logic with Ref for Images avoiding closure issues
    const imagesRef = useRef([]);
    // Override captureFrame to push to ref
    const captureFrameRef = () => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (video && canvas) {
            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            canvas.toBlob(blob => {
                imagesRef.current.push(blob);
            }, 'image/jpeg');
        }
    };

    const startCaptureRef = () => {
        if (!name) { alert("Enter Name"); return; }
        setCapturing(true);
        imagesRef.current = [];
        setProgress(0);
        setStatus("Capturing...");

        let count = 0;
        const interval = setInterval(() => {
            if (count >= 20) {
                clearInterval(interval);
                setCapturing(false);
                setStatus("Submitting...");
                finalSubmit();
                return;
            }
            captureFrameRef();
            count++;
            setProgress(count);
        }, 300);
    };

    const finalSubmit = async () => {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('role', role);
        formData.append('flat_number', flatNumber);

        imagesRef.current.forEach((blob, i) => {
            formData.append('files', blob, `sample_${i}.jpg`);
        });

        try {
            const res = await fetch('http://localhost:8000/register/', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                setStatus(`Success: ${data.message}`);
                alert("Registration Successful!");
                // Reload page or clear form
                window.location.reload();
            } else {
                setStatus(`Error: ${data.detail}`);
            }
        } catch (err) {
            setStatus(`Network Error: ${err}`);
        }
    };

    return (
        <div className="p-6 bg-slate-900 min-h-screen text-white flex flex-col items-center">
            <h1 className="text-3xl font-bold mb-6 text-emerald-400">User Registration</h1>

            <div className="flex gap-8 w-full max-w-4xl">
                {/* Form */}
                <div className="flex-1 bg-slate-800 p-6 rounded-xl border border-slate-700">
                    <div className="mb-4">
                        <label className="block text-slate-400 mb-2">Full Name</label>
                        <input
                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white"
                            value={name} onChange={e => setName(e.target.value)}
                        />
                    </div>

                    <div className="mb-4">
                        <label className="block text-slate-400 mb-2">Role</label>
                        <select
                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white"
                            value={role} onChange={e => setRole(e.target.value)}
                        >
                            <option value="resident">Resident</option>
                            <option value="staff">Staff</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>

                    <div className="mb-4">
                        <label className="block text-slate-400 mb-2">Flat Number (Optional)</label>
                        <input
                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-white"
                            value={flatNumber} onChange={e => setFlatNumber(e.target.value)}
                        />
                    </div>

                    <button
                        onClick={startCaptureRef}
                        disabled={capturing}
                        className={`w-full py-3 rounded font-bold transition ${capturing ? 'bg-gray-600' : 'bg-emerald-500 hover:bg-emerald-600'}`}
                    >
                        {capturing ? `Capturing... ${Math.round((progress / 20) * 100)}%` : 'Start Registration'}
                    </button>

                    <p className="mt-4 text-center text-yellow-400">{status}</p>
                </div>

                {/* Camera Preview */}
                <div className="flex-1 bg-black rounded-xl overflow-hidden relative border border-slate-700 h-[400px]">
                    <video ref={videoRef} autoPlay muted className="w-full h-full object-cover"></video>
                    <canvas ref={canvasRef} className="hidden"></canvas>

                    {/* Overlay */}
                    <div className="absolute top-4 right-4 bg-black/50 px-3 py-1 rounded text-sm">
                        Face Samples: {progress} / 20
                    </div>

                    {capturing && (
                        <div className="absolute inset-0 border-4 border-emerald-500 animate-pulse pointer-events-none"></div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Register;
