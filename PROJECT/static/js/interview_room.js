// Interview Room WebRTC Implementation
class InterviewRoom {
    constructor(roomId, roomCode, userRole, username) {
        this.roomId = roomId;
        this.roomCode = roomCode;
        this.userRole = userRole;
        this.username = username;
        this.localStream = null;
        this.screenStream = null;
        this.peers = {}; // sid -> RTCPeerConnection
        this.sidToUsername = {}; // sid -> username for UI
        this.socket = io();
        this.isMuted = false;
        this.isScreenSharing = false;
        
        console.log('Interview room initialized:', { roomId, roomCode, userRole, username });
        
        this.initializeSocket();
        this.initializeUI();
        this.initializeCodeEditor();
    }

    initializeSocket() {
        // Join the interview room
        this.socket.emit('join_interview', {
            room: this.roomId,
            room_code: this.roomCode,
            role: this.userRole
        });

        // Handle existing participants
        this.socket.on('participants', (data) => {
            console.log('Received participants:', data.participants);
            const list = Array.isArray(data.participants) ? data.participants : [];
            
            // Add users to list first
            list.forEach(p => {
                this.sidToUsername[p.sid] = p.username;
                this.addUserToList(p.sid, p.username, p.role);
            });
            
            // Then create offers with proper delay
            list.forEach(p => {
                setTimeout(() => {
                    this.createOffer(p.sid);
                }, 1500); // Increased delay
            });
        });

        // Handle user joined
        this.socket.on('user_joined', (data) => {
            if (!data || !data.sid) return;
            if (data.sid === this.socket.id) return; // ignore self
            
            console.log('User joined:', data.username, data.sid);
            this.sidToUsername[data.sid] = data.username;
            this.addUserToList(data.sid, data.username, data.role);
            
            // Create offer for new peer with proper timing
            setTimeout(() => {
                this.createOffer(data.sid);
            }, 2000);
        });

        // Handle user left
        this.socket.on('user_left', (data) => {
            if (!data || !data.sid) return;
            console.log('User left:', data.username, data.sid);
            this.removeUserFromList(data.sid);
            this.removePeer(data.sid);
            delete this.sidToUsername[data.sid];
        });

        // WebRTC signaling
        this.socket.on('offer', (data) => {
            if (!data || !data.from) return;
            console.log('Received offer from:', data.from);
            this.handleOffer(data.offer, data.from);
        });

        this.socket.on('answer', (data) => {
            if (!data || !data.from) return;
            console.log('Received answer from:', data.from);
            this.handleAnswer(data.answer, data.from);
        });

        this.socket.on('ice_candidate', (data) => {
            if (!data || !data.from) return;
            console.log('Received ICE candidate from:', data.from);
            this.handleIceCandidate(data.candidate, data.from);
        });

        // Code editor events
        this.socket.on('code_updated', (data) => {
            if (data.from !== this.socket.id) {
                const codeEditor = document.getElementById('codeEditor');
                const languageSelect = document.getElementById('languageSelect');
                if (codeEditor) codeEditor.value = data.code;
                if (languageSelect) languageSelect.value = data.language;
            }
        });
    }

    initializeUI() {
        // Get DOM elements
        this.localVideo = document.getElementById('localVideo');
        this.muteBtn = document.getElementById('muteBtn');
        this.screenShareBtn = document.getElementById('screenShareBtn');
        this.endCallBtn = document.getElementById('endCallBtn');
        this.membersList = document.getElementById('membersList');
        this.waitingMessage = document.getElementById('waitingMessage');

        // Add event listeners
        if (this.muteBtn) this.muteBtn.addEventListener('click', () => this.toggleMute());
        if (this.screenShareBtn) this.screenShareBtn.addEventListener('click', () => this.toggleScreenShare());
        if (this.endCallBtn) this.endCallBtn.addEventListener('click', () => this.endCall());

        // Initialize local video
        this.startLocalVideo();
    }

    async startLocalVideo() {
        try {
            this.localStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            if (this.localVideo) {
                this.localVideo.srcObject = this.localStream;
                this.localVideo.play().catch(e => console.log('Local video autoplay prevented'));
            }
            console.log('Local video started');
        } catch (error) {
            console.error('Error accessing media devices:', error);
            // Try audio-only fallback
            try {
                this.localStream = await navigator.mediaDevices.getUserMedia({
                    audio: true,
                    video: false
                });
                console.log('Audio-only mode activated');
            } catch (audioError) {
                console.error('Error accessing audio:', audioError);
                alert('Please allow camera and microphone access to participate in the interview');
            }
        }
    }

    async createPeerConnection(sid) {
        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' }
            ],
            iceCandidatePoolSize: 10
        };

        const peerConnection = new RTCPeerConnection(configuration);

        // Add local stream tracks FIRST
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => {
                console.log('Adding local track:', track.kind, 'to peer:', sid);
                peerConnection.addTrack(track, this.localStream);
            });
        }

        // Handle connection state changes
        peerConnection.onconnectionstatechange = () => {
            console.log(`Connection state with ${sid}:`, peerConnection.connectionState);
            if (peerConnection.connectionState === 'failed') {
                console.log('Connection failed, attempting to restart ICE');
                peerConnection.restartIce();
            }
        };

        // Handle ICE connection state
        peerConnection.oniceconnectionstatechange = () => {
            console.log(`ICE connection state with ${sid}:`, peerConnection.iceConnectionState);
        };

        // Handle ICE candidates
        peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                console.log('Sending ICE candidate to:', sid);
                this.socket.emit('ice_candidate', {
                    to: sid,
                    candidate: event.candidate
                });
            } else {
                console.log('All ICE candidates sent for:', sid);
            }
        };

        // Handle remote stream - FIXED VERSION
        peerConnection.ontrack = (event) => {
            console.log('Received remote track from:', sid, 'kind:', event.track.kind);
            if (event.streams && event.streams[0]) {
                // Pass the first stream, not the streams array
                this.addRemoteVideo(sid, event.streams[0]);
            }
        };

        return peerConnection;
    }

    async createOffer(sid) {
        let peerConnection = this.peers[sid];
        if (!peerConnection) {
            peerConnection = await this.createPeerConnection(sid);
            this.peers[sid] = peerConnection;
        }

        try {
            const offer = await peerConnection.createOffer({
                offerToReceiveAudio: true,
                offerToReceiveVideo: true
            });
            await peerConnection.setLocalDescription(offer);
            
            console.log('Sending offer to:', sid);
            this.socket.emit('offer', { 
                to: sid, 
                offer: offer 
            });
        } catch (error) {
            console.error('Error creating offer for', sid, error);
        }
    }

    async handleOffer(offer, fromSid) {
        let peerConnection = this.peers[fromSid];
        if (!peerConnection) {
            peerConnection = await this.createPeerConnection(fromSid);
            this.peers[fromSid] = peerConnection;
        }

        try {
            const remoteDesc = new RTCSessionDescription(offer);
            
            if (peerConnection.signalingState === 'have-local-offer') {
                // Rollback local offer to accept remote offer (glare handling)
                await peerConnection.setLocalDescription({ type: 'rollback' });
            }
            
            await peerConnection.setRemoteDescription(remoteDesc);
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            
            console.log('Sending answer to:', fromSid);
            this.socket.emit('answer', { 
                to: fromSid, 
                answer: answer 
            });
        } catch (error) {
            console.error('Error handling offer from', fromSid, error);
        }
    }

    async handleAnswer(answer, fromSid) {
        const peerConnection = this.peers[fromSid];
        if (peerConnection) {
            try {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
                console.log('Answer processed for:', fromSid);
            } catch (error) {
                console.error('Error handling answer from', fromSid, error);
            }
        }
    }

    async handleIceCandidate(candidate, fromSid) {
        const peerConnection = this.peers[fromSid];
        if (peerConnection && peerConnection.remoteDescription) {
            try {
                await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
                console.log('ICE candidate added for:', fromSid);
            } catch (error) {
                console.error('Error adding ICE candidate from', fromSid, error);
            }
        }
    }

    // FIXED addRemoteVideo function
    addRemoteVideo(sid, stream) {
        console.log('Adding remote video for:', sid, stream);
        
        // Remove existing video for this participant
        const existingWrapper = document.getElementById(`remote-wrapper-${sid}`);
        if (existingWrapper) {
            existingWrapper.remove();
        }
        
        // Get or create remote videos container
        let remoteContainer = document.getElementById('remoteVideos');
        if (!remoteContainer) {
            remoteContainer = this.createRemoteVideoContainer();
        }
        
        // Create video wrapper
        const videoWrapper = document.createElement('div');
        videoWrapper.className = 'remote-video-wrapper';
        videoWrapper.id = `remote-wrapper-${sid}`;
        
        // Create video element
        const remoteVideo = document.createElement('video');
        remoteVideo.id = `remote-video-${sid}`;
        remoteVideo.className = 'remote-video';
        remoteVideo.autoplay = true;
        remoteVideo.playsInline = true;
        remoteVideo.muted = false;
        remoteVideo.srcObject = stream;
        
        // Create username label
        const usernameLabel = document.createElement('div');
        usernameLabel.className = 'video-label';
        usernameLabel.textContent = this.sidToUsername[sid] || 'Remote User';
        
        // Assemble the structure
        videoWrapper.appendChild(remoteVideo);
        videoWrapper.appendChild(usernameLabel);
        remoteContainer.appendChild(videoWrapper);
        
        // Hide waiting message
        if (this.waitingMessage) {
            this.waitingMessage.style.display = 'none';
        }
        
        // Try to play video
        remoteVideo.play().catch(e => {
            console.log('Remote video autoplay prevented for:', sid);
        });
        
        console.log('Remote video added successfully for:', sid);
    }

    createRemoteVideoContainer() {
        let container = document.getElementById('remoteVideos');
        if (!container) {
            container = document.createElement('div');
            container.id = 'remoteVideos';
            container.className = 'remote-videos-container';
            
            // Find the video container and add remote videos container
            const mainVideoContainer = document.querySelector('.video-container');
            if (mainVideoContainer) {
                mainVideoContainer.appendChild(container);
            }
        }
        return container;
    }

    addUserToList(sid, username, role) {
        if (!sid) return;
        const memberId = `member-${sid}`;
        if (document.getElementById(memberId)) return;

        const membersList = document.getElementById('membersList');
        if (!membersList) return;

        const memberItem = document.createElement('div');
        memberItem.className = 'member-item';
        memberItem.id = memberId;
        memberItem.innerHTML = `
            <div class="member-info">
                <span class="member-name">${username}</span>
                <span class="member-role badge ${role}">${role}</span>
            </div>
        `;

        membersList.appendChild(memberItem);
    }

    removeUserFromList(sid) {
        const memberItem = document.getElementById(`member-${sid}`);
        if (memberItem) {
            memberItem.remove();
        }
        
        // Remove remote video wrapper
        const remoteWrapper = document.getElementById(`remote-wrapper-${sid}`);
        if (remoteWrapper) {
            remoteWrapper.remove();
        }
        
        // Show waiting message if no remote videos left
        const remoteContainer = document.getElementById('remoteVideos');
        if (remoteContainer && remoteContainer.children.length === 0 && this.waitingMessage) {
            this.waitingMessage.style.display = 'block';
        }
    }

    removePeer(sid) {
        if (this.peers[sid]) {
            this.peers[sid].close();
            delete this.peers[sid];
            console.log('Peer connection closed for:', sid);
        }
    }

    toggleMute() {
        if (this.localStream) {
            const audioTrack = this.localStream.getAudioTracks()[0];
            if (audioTrack) {
                audioTrack.enabled = !audioTrack.enabled;
                this.isMuted = !audioTrack.enabled;
                
                if (this.muteBtn) {
                    this.muteBtn.innerHTML = this.isMuted ? 
                        '<i class="fas fa-microphone-slash"></i> Unmute' : 
                        '<i class="fas fa-microphone"></i> Mute';
                    this.muteBtn.classList.toggle('muted', this.isMuted);
                }
            }
        }
    }

    async toggleScreenShare() {
        if (!this.isScreenSharing) {
            try {
                this.screenStream = await navigator.mediaDevices.getDisplayMedia({
                    video: true,
                    audio: true
                });

                // Replace video track in all peer connections
                const videoTrack = this.screenStream.getVideoTracks()[0];
                for (const [sid, peerConnection] of Object.entries(this.peers)) {
                    const sender = peerConnection.getSenders().find(s => 
                        s.track && s.track.kind === 'video'
                    );
                    if (sender) {
                        await sender.replaceTrack(videoTrack);
                    }
                }

                // Update local video
                if (this.localVideo) {
                    this.localVideo.srcObject = this.screenStream;
                }

                this.isScreenSharing = true;
                if (this.screenShareBtn) {
                    this.screenShareBtn.innerHTML = '<i class="fas fa-desktop"></i> Stop Sharing';
                    this.screenShareBtn.classList.add('sharing');
                }

                // Handle screen share ending
                videoTrack.onended = () => {
                    this.stopScreenShare();
                };
            } catch (error) {
                console.error('Error starting screen share:', error);
            }
        } else {
            this.stopScreenShare();
        }
    }

    async stopScreenShare() {
        if (this.screenStream) {
            this.screenStream.getTracks().forEach(track => track.stop());
            this.screenStream = null;
        }

        // Replace screen share track with camera track
        if (this.localStream) {
            const videoTrack = this.localStream.getVideoTracks()[0];
            for (const [sid, peerConnection] of Object.entries(this.peers)) {
                const sender = peerConnection.getSenders().find(s => 
                    s.track && s.track.kind === 'video'
                );
                if (sender && videoTrack) {
                    await sender.replaceTrack(videoTrack);
                }
            }

            // Update local video
            if (this.localVideo) {
                this.localVideo.srcObject = this.localStream;
            }
        }

        this.isScreenSharing = false;
        if (this.screenShareBtn) {
            this.screenShareBtn.innerHTML = '<i class="fas fa-desktop"></i> Share Screen';
            this.screenShareBtn.classList.remove('sharing');
        }
    }

    endCall() {
        // Clean up all peer connections
        Object.values(this.peers).forEach(pc => pc.close());
        this.peers = {};

        // Stop all tracks
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
        }
        if (this.screenStream) {
            this.screenStream.getTracks().forEach(track => track.stop());
        }

        // Leave socket room
        this.socket.emit('leave_interview', { room: this.roomId });

        // Redirect
        window.location.href = '/';
    }

    // Code editor functionality
    initializeCodeEditor() {
        const codeEditor = document.getElementById('codeEditor');
        const languageSelect = document.getElementById('languageSelect');
        const runCodeBtn = document.getElementById('runCode');

        if (codeEditor) {
            let debounceTimer;
            codeEditor.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.socket.emit('code_change', {
                        room: this.roomId,
                        code: codeEditor.value,
                        language: languageSelect ? languageSelect.value : 'javascript'
                    });
                }, 500);
            });
        }

        if (languageSelect) {
            languageSelect.addEventListener('change', () => {
                if (codeEditor) {
                    this.socket.emit('code_change', {
                        room: this.roomId,
                        code: codeEditor.value,
                        language: languageSelect.value
                    });
                }
            });
        }

        if (runCodeBtn) {
            runCodeBtn.addEventListener('click', () => {
                this.executeCode();
            });
        }
    }

    async executeCode() {
        const codeEditor = document.getElementById('codeEditor');
        const languageSelect = document.getElementById('languageSelect');
        const outputDiv = document.getElementById('output');

        if (!codeEditor) return;

        const code = codeEditor.value.trim();
        const language = languageSelect ? languageSelect.value : 'javascript';

        if (!code) {
            if (outputDiv) outputDiv.textContent = 'Please enter some code to execute.';
            return;
        }

        if (outputDiv) outputDiv.textContent = 'Executing code...';

        try {
            const response = await fetch('/api/execute_code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    code: code,
                    language: language
                })
            });

            const result = await response.json();

            if (outputDiv) {
                if (result.error) {
                    outputDiv.textContent = `Error: ${result.error}`;
                } else {
                    outputDiv.textContent = result.output || 'Code executed successfully (no output)';
                }
            }
        } catch (error) {
            console.error('Error executing code:', error);
            if (outputDiv) outputDiv.textContent = `Execution failed: ${error.message}`;
        }
    }

    // Debug function
    debugConnections() {
        console.log('=== Connection Debug Info ===');
        console.log('Local stream:', this.localStream);
        console.log('Number of peers:', Object.keys(this.peers).length);
        
        Object.entries(this.peers).forEach(([sid, pc]) => {
            console.log(`Peer ${sid}:`);
            console.log('  Connection State:', pc.connectionState);
            console.log('  ICE Connection State:', pc.iceConnectionState);
            console.log('  Signaling State:', pc.signalingState);
            
            pc.getStats().then(stats => {
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.mediaType === 'video') {
                        console.log(`  Video bytes received: ${report.bytesReceived}`);
                    }
                });
            });
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get room data from template
    const roomData = window.interviewRoomData;
    if (roomData) {
        window.interviewRoom = new InterviewRoom(
            roomData.roomId,
            roomData.roomCode,
            roomData.userRole,
            roomData.username
        );
        
        // Expose debug function globally
        window.debugConnections = () => window.interviewRoom.debugConnections();
        
        console.log('Interview room initialized successfully');
    } else {
        console.error('Room data not found!');
    }
});