const token = sessionStorage.getItem('admin_token');
const loginView = document.getElementById('login-view');
const dashView = document.getElementById('dashboard-view');

if (token) {
    loginView.classList.add('hidden');
    dashView.classList.remove('hidden');
}

const adminConfidenceToggle = document.getElementById('admin-confidence-60-toggle');
if (adminConfidenceToggle) {
    adminConfidenceToggle.checked = localStorage.getItem('attendance-confidence-policy') === 'strict_60';
    adminConfidenceToggle.addEventListener('change', () => {
        localStorage.setItem(
            'attendance-confidence-policy',
            adminConfidenceToggle.checked ? 'strict_60' : 'standard'
        );
        showToast(
            adminConfidenceToggle.checked ? '60% confidence policy enabled' : 'Standard confidence policy enabled',
            'toast-success'
        );
    });
}

function showToast(message, type = 'toast-info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    let iconName = 'info';
    if (type === 'toast-success') iconName = 'check-circle';
    else if (type === 'toast-warning') iconName = 'alert-triangle';
    else if (type === 'toast-error') iconName = 'x-circle';

    toast.innerHTML = `<i data-lucide="${iconName}" class="toast-icon"></i><span class="toast-message">${message}</span>`;
    container.appendChild(toast);
    lucide.createIcons();
    setTimeout(() => {
        toast.classList.add('toast-fadeOut');
        setTimeout(() => { if (toast.parentElement) toast.parentElement.removeChild(toast); }, 300);
    }, 4000);
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = document.getElementById('admin-password').value;
    try {
        const res = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        const data = await res.json();
        if (res.ok) {
            sessionStorage.setItem('admin_token', data.token);
            window.location.reload();
        } else {
            showToast(data.detail, 'toast-error');
        }
    } catch (err) {
        showToast('Login failed', 'toast-error');
    }
});

const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        sessionStorage.removeItem('admin_token');
        window.location.reload();
    });
}

async function adminFetch(url, options = {}) {
    const t = sessionStorage.getItem('admin_token');
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${t}`,
        'Content-Type': 'application/json'
    };
    const res = await fetch(url, options);
    if (res.status === 401) {
        sessionStorage.removeItem('admin_token');
        window.location.reload();
    }
    return res;
}

document.getElementById('manual-log-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const reg_no = document.getElementById('manual-reg').value;
    const mode = document.getElementById('manual-mode').value;
    const res = await adminFetch('/api/admin/manual_log', {
        method: 'POST',
        body: JSON.stringify({ reg_no, mode })
    });
    if (res.ok) {
        showToast(`Manually logged ${reg_no}`, 'toast-success');
        document.getElementById('manual-reg').value = '';
    } else {
        const data = await res.json();
        showToast(data.detail, 'toast-error');
    }
});

document.getElementById('edit-log-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const reg_no = document.getElementById('edit-reg').value;
    const date = document.getElementById('edit-date').value;
    const check_in_time = document.getElementById('edit-in').value || null;
    const check_out_time = document.getElementById('edit-out').value || null;

    // Add seconds if not present
    const formatTime = (t) => t && t.split(':').length === 2 ? t + ':00' : t;

    const res = await adminFetch('/api/admin/attendance/edit', {
        method: 'POST',
        body: JSON.stringify({
            reg_no,
            date,
            check_in_time: formatTime(check_in_time),
            check_out_time: formatTime(check_out_time)
        })
    });
    if (res.ok) {
        showToast(`Log updated for ${reg_no}`, 'toast-success');
        document.getElementById('edit-in').value = '';
        document.getElementById('edit-out').value = '';
    } else {
        const data = await res.json();
        showToast(data.detail, 'toast-error');
    }
});

document.getElementById('cooldown-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const reg_no = document.getElementById('cooldown-reg').value;
    const res = await adminFetch('/api/admin/cooldown/release', {
        method: 'POST',
        body: JSON.stringify({ reg_no })
    });
    if (res.ok) {
        const data = await res.json();
        showToast(data.message || `Cooldown released`, 'toast-success');
        document.getElementById('cooldown-reg').value = '';
    } else {
        showToast('Failed to release', 'toast-error');
    }
});

document.getElementById('remove-user-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const reg_no = document.getElementById('remove-reg').value;
    if (!confirm(`Are you absolutely sure you want to delete user ${reg_no} and ALL their history?`)) return;
    const res = await adminFetch(`/api/admin/students/${reg_no}`, {
        method: 'DELETE'
    });
    if (res.ok) {
        showToast(`Deleted user ${reg_no}`, 'toast-success');
        document.getElementById('remove-reg').value = '';
    } else {
        const data = await res.json();
        showToast(data.detail, 'toast-error');
    }
});

document.getElementById('force-checkout-active-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!confirm('Are you sure you want to force check-out all students who are currently checked in?')) return;
    const res = await adminFetch('/api/admin/session/force_checkout_active', {
        method: 'POST'
    });
    if (res.ok) {
        const data = await res.json();
        showToast(data.message || 'Force checkout complete', 'toast-success');
    } else {
        const data = await res.json();
        showToast(data.detail || 'Failed to force checkout', 'toast-error');
    }
});

document.getElementById('end-session-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!confirm('Are you sure you want to end the session? This will mark all users who have not checked out as absent.')) return;
    const res = await adminFetch('/api/admin/session/end', {
        method: 'POST'
    });
    if (res.ok) {
        const data = await res.json();
        showToast(data.message || 'Session ended successfully', 'toast-success');
    } else {
        const data = await res.json();
        showToast(data.detail || 'Failed to end session', 'toast-error');
    }
});


async function autoFillEditLog() {
    const reg_no = document.getElementById('edit-reg').value.trim().toUpperCase();
    const date = document.getElementById('edit-date').value;

    if (reg_no && date) {
        try {
            const res = await fetch(`/api/attendance?date=${date}`);
            if (res.ok) {
                const logs = await res.json();
                const log = logs.find(l => l.reg_no === reg_no);
                if (log) {
                    document.getElementById('edit-in').value = log.check_in_time || '';
                    document.getElementById('edit-out').value = (log.check_out_time && log.check_out_time !== 'MISSED' ? log.check_out_time : '') || '';
                    showToast(`Loaded log for ${reg_no}`, 'toast-success');
                } else {
                    document.getElementById('edit-in').value = '';
                    document.getElementById('edit-out').value = '';
                }
            }
        } catch (e) {
            console.error('Failed to auto-fill:', e);
        }
    }
}

document.getElementById('edit-reg').addEventListener('blur', autoFillEditLog);
document.getElementById('edit-reg').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        autoFillEditLog();
    }
});
document.getElementById('edit-date').addEventListener('change', autoFillEditLog);

// Set today's date for edit log
const _d = new Date();
const today = `${_d.getFullYear()}-${String(_d.getMonth() + 1).padStart(2, '0')}-${String(_d.getDate()).padStart(2, '0')}`;
const editDate = document.getElementById('edit-date');
if (editDate) editDate.value = today;

// --- Private Face Registration Logic ---
let adminStream = null;
let adminCaptureTimer = null;
let adminCountdownTimer = null;

async function startAdminCamera() {
    try {
        adminStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
            audio: false
        });
        const video = document.getElementById('admin-video');
        video.srcObject = adminStream;
        return true;
    } catch (e) {
        showToast('Camera access denied or unavailable', 'toast-error');
        return false;
    }
}

function stopAdminCamera() {
    if (adminStream) {
        adminStream.getTracks().forEach(track => track.stop());
        adminStream = null;
    }
    const video = document.getElementById('admin-video');
    if (video) video.srcObject = null;

    if (adminCaptureTimer) clearInterval(adminCaptureTimer);
    if (adminCountdownTimer) clearInterval(adminCountdownTimer);
}

document.getElementById('admin-register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const regNo = document.getElementById('admin-reg-no').value.trim().toUpperCase();
    if (!regNo) return;

    const container = document.getElementById('admin-camera-container');
    const btn = document.getElementById('btn-start-reg');
    const progressContainer = document.getElementById('admin-progress-container');
    const countdownOverlay = document.getElementById('admin-countdown-overlay');
    const countdownNumber = document.getElementById('admin-countdown-number');
    const progressBar = document.getElementById('admin-progress-bar');
    const progressText = document.getElementById('admin-progress-text');

    container.classList.remove('hidden');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader"></i> Initializing...';
    lucide.createIcons();

    const cameraStarted = await startAdminCamera();
    if (!cameraStarted) {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="video"></i> Start Camera';
        container.classList.add('hidden');
        lucide.createIcons();
        return;
    }

    btn.innerHTML = '<i data-lucide="camera"></i> Capturing...';
    lucide.createIcons();

    progressContainer.style.display = 'block';
    countdownOverlay.style.display = 'flex';

    let countdownVal = 6;
    countdownNumber.innerText = countdownVal;
    progressBar.style.width = '0%';
    progressText.innerText = '0%';

    const capturedImages = [];
    const maxCaptures = 10;
    const captureInterval = 600;
    let captureCount = 0;

    adminCountdownTimer = setInterval(() => {
        countdownVal--;
        countdownNumber.innerText = countdownVal;
        if (countdownVal <= 0) {
            clearInterval(adminCountdownTimer);
            countdownOverlay.style.display = 'none';
        }
    }, 1000);

    adminCaptureTimer = setInterval(async () => {
        captureCount++;

        const video = document.getElementById('admin-video');
        const canvas = document.getElementById('admin-canvas');
        const ctx = canvas.getContext('2d');

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;

        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.setTransform(1, 0, 0, 1, 0, 0);

        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        capturedImages.push(dataUrl);

        const percent = Math.round((captureCount / maxCaptures) * 100);
        progressBar.style.width = `${percent}%`;
        progressText.innerText = `${percent}%`;

        if (captureCount >= maxCaptures) {
            clearInterval(adminCaptureTimer);
            stopAdminCamera();
            container.classList.add('hidden');

            btn.innerHTML = '<i data-lucide="loader"></i> Processing...';
            lucide.createIcons();

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reg_no: regNo, images: capturedImages })
                });
                const data = await res.json();

                if (res.ok) {
                    showToast(`Successfully registered & checked in ${regNo}`, 'toast-success');
                    document.getElementById('admin-reg-no').value = '';
                    if (typeof loadFaceRegistry === 'function') loadFaceRegistry();
                    if (typeof loadAdminLogs === 'function') loadAdminLogs();
                } else {
                    showToast(data.detail || 'Registration failed', 'toast-error');
                }
            } catch (err) {
                showToast('Network error during registration', 'toast-error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="video"></i> Start Camera';
                lucide.createIcons();
            }
        }
    }, captureInterval);
});

// --- CSV Drag and Drop Upload Logic ---
const dropZone = document.getElementById('csv-drop-zone');
const fileInput = document.getElementById('csv-file-input');
const uploadStatus = document.getElementById('csv-upload-status');

if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.background = 'rgba(37, 99, 235, 0.2)';
        dropZone.style.borderColor = 'var(--color-primary)';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.background = 'rgba(0,0,0,0.1)';
        dropZone.style.borderColor = 'var(--color-gray-600)';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.background = 'rgba(0,0,0,0.1)';
        dropZone.style.borderColor = 'var(--color-gray-600)';

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (!file.name.endsWith('.csv')) {
            showToast('Only CSV files are allowed', 'toast-error');
            return;
        }

        uploadStatus.style.display = 'block';
        uploadStatus.style.color = 'var(--color-primary)';
        uploadStatus.innerHTML = '<i data-lucide="loader"></i> Uploading...';
        lucide.createIcons();

        const formData = new FormData();
        formData.append('file', file);

        try {
            const t = sessionStorage.getItem('admin_token');
            const res = await fetch('/api/admin/upload_students_csv', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${t}`
                },
                body: formData
            });

            if (res.status === 401) {
                sessionStorage.removeItem('admin_token');
                window.location.reload();
                return;
            }

            const data = await res.json();
            if (res.ok) {
                uploadStatus.style.color = 'var(--color-success)';
                uploadStatus.innerText = `Success! Imported ${data.imported} student records.`;
                showToast(`Imported ${data.imported} students`, 'toast-success');
            } else {
                uploadStatus.style.color = 'var(--color-danger)';
                uploadStatus.innerText = `Error: ${data.detail || 'Upload failed'}`;
                showToast(data.detail || 'Upload failed', 'toast-error');
            }
        } catch (err) {
            uploadStatus.style.color = 'var(--color-danger)';
            uploadStatus.innerText = 'Network error during upload.';
            showToast('Network error during upload', 'toast-error');
        }

        // Reset file input so same file can be selected again
        fileInput.value = '';
    }
}

// --- Face Embeddings Registry Logic ---
let allStudentsCache = [];

async function loadFaceRegistry() {
    const tbody = document.getElementById('face-embeddings-tbody');
    const badge = document.getElementById('face-embeddings-summary-badge');
    if (!tbody) return;

    try {
        const res = await fetch('/api/students');
        if (!res.ok) throw new Error('Failed to fetch students');

        allStudentsCache = await res.json();
        renderFaceRegistry();
    } catch (err) {
        console.error('Error loading face registry:', err);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--color-danger);">Failed to load face registry.</td></tr>`;
        }
    }
}

function renderFaceRegistry() {
    const tbody = document.getElementById('face-embeddings-tbody');
    const badge = document.getElementById('face-embeddings-summary-badge');
    const searchVal = (document.getElementById('face-search-input')?.value || '').trim().toLowerCase();
    const filterVal = document.getElementById('face-filter-select')?.value || 'all';

    if (!tbody) return;

    const registeredCount = allStudentsCache.filter(s => s.has_face).length;
    const totalCount = allStudentsCache.length;

    if (badge) {
        badge.innerHTML = `<i data-lucide="check-circle-2" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;"></i> ${registeredCount} / ${totalCount} Enrolled`;
        if (window.lucide) lucide.createIcons();
    }

    let filtered = allStudentsCache.filter(s => {
        const matchesSearch = !searchVal ||
            s.reg_no.toLowerCase().includes(searchVal) ||
            (s.name || '').toLowerCase().includes(searchVal) ||
            (s.department || '').toLowerCase().includes(searchVal);

        if (!matchesSearch) return false;

        if (filterVal === 'registered') return s.has_face;
        if (filterVal === 'missing') return !s.has_face;
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-secondary);">No student records found matching filters.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(s => {
        const statusBadge = s.has_face
            ? `<span style="background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3); padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;"><i data-lucide="check-circle-2" style="width: 13px; height: 13px;"></i> Enrolled</span>`
            : `<span style="background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;"><i data-lucide="alert-triangle" style="width: 13px; height: 13px;"></i> No Face Registered</span>`;

        return `
            <tr style="border-bottom: 1px solid var(--color-gray-800);">
                <td style="padding: 10px 14px; font-weight: 600; color: white;">${s.reg_no}</td>
                <td style="padding: 10px 14px;">${s.name || '-'}</td>
                <td style="padding: 10px 14px; color: var(--text-secondary);">${s.department || '-'}</td>
                <td style="padding: 10px 14px; color: var(--text-secondary);">${s.shift || 'Shift 1'}</td>
                <td style="padding: 10px 14px; text-align: center;">${statusBadge}</td>
            </tr>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

// Event Listeners for Face Registry
if (dashView && !dashView.classList.contains('hidden')) {
    loadFaceRegistry();
    loadAdminCooldowns();
    setInterval(loadAdminCooldowns, 3000);
}

document.getElementById('refresh-face-list-btn')?.addEventListener('click', loadFaceRegistry);
document.getElementById('face-search-input')?.addEventListener('input', renderFaceRegistry);
document.getElementById('face-filter-select')?.addEventListener('change', renderFaceRegistry);

// --- Active Cooldowns Management ---
let allCooldownsCache = [];

async function loadAdminCooldowns() {
    const tbody = document.getElementById('cooldown-tbody');
    if (!tbody) return;

    try {
        const res = await adminFetch('/api/admin/cooldowns');
        if (!res.ok) return;
        allCooldownsCache = await res.json();
        renderAdminCooldowns();
    } catch (err) {
        console.error("Failed to load active cooldowns:", err);
    }
}

function renderAdminCooldowns() {
    const tbody = document.getElementById('cooldown-tbody');
    const badge = document.getElementById('cooldown-summary-badge');
    const searchVal = (document.getElementById('cooldown-search-input')?.value || '').toLowerCase().trim();

    if (!tbody) return;

    if (badge) {
        badge.innerHTML = `<i data-lucide="snowflake" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;"></i> ${allCooldownsCache.length} Active`;
    }

    const filtered = allCooldownsCache.filter(c => {
        return (c.reg_no || '').toLowerCase().includes(searchVal) ||
            (c.name || '').toLowerCase().includes(searchVal) ||
            (c.department || '').toLowerCase().includes(searchVal);
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-secondary);">No active cooldowns found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(c => {
        const mins = Math.floor(c.cooldown_remaining / 60);
        const secs = c.cooldown_remaining % 60;
        const timeStr = mins > 0 ? `${mins}m ${secs}s remaining` : `${secs}s remaining`;

        return `
            <tr style="border-bottom: 1px solid var(--color-gray-800);">
                <td style="padding: 10px 14px; font-weight: 600; color: white;">${c.reg_no}</td>
                <td style="padding: 10px 14px;">${c.name || '-'}</td>
                <td style="padding: 10px 14px; color: var(--text-secondary);">${c.department || '-'}</td>
                <td style="padding: 10px 14px;"><span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; font-weight: 600;">${timeStr}</span></td>
                <td style="padding: 10px 14px; text-align: center;">
                    <button class="btn btn-secondary btn-sm remove-single-cooldown-btn" data-reg="${c.reg_no}" style="padding: 4px 10px; font-size: 12px;">
                        <i data-lucide="zap" style="width: 12px; height: 12px;"></i> Release
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();

    document.querySelectorAll('.remove-single-cooldown-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const regNo = e.currentTarget.getAttribute('data-reg');
            if (!regNo) return;
            try {
                const res = await adminFetch(`/api/admin/cooldown/${encodeURIComponent(regNo)}`, { method: 'DELETE' });
                if (res.ok) {
                    showToast(`Released cooldown for ${regNo}`, 'toast-success');
                    loadAdminCooldowns();
                } else {
                    showToast(`Failed to release cooldown for ${regNo}`, 'toast-error');
                }
            } catch (err) {
                showToast('Network error clearing cooldown', 'toast-error');
            }
        });
    });
}

document.getElementById('clear-all-cooldowns-btn')?.addEventListener('click', async () => {
    const password = prompt("Centralized Override: Enter root admin password to clear ALL active user cooldowns:");
    if (password === null) return;

    if (!password) {
        showToast("Password is required to clear all cooldowns.", "toast-error");
        return;
    }

    try {
        const res = await adminFetch('/api/admin/cooldowns/clear-all', {
            method: 'POST',
            body: JSON.stringify({ password })
        });
        const data = await res.json();
        if (res.ok) {
            showToast("All active cooldowns cleared successfully!", "toast-success");
            loadAdminCooldowns();
        } else {
            showToast(data.detail || "Failed to clear all cooldowns.", "toast-error");
        }
    } catch (err) {
        showToast("Network error clearing all cooldowns", "toast-error");
    }
});

document.getElementById('refresh-cooldown-list-btn')?.addEventListener('click', loadAdminCooldowns);
document.getElementById('cooldown-search-input')?.addEventListener('input', renderAdminCooldowns);

