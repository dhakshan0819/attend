// Global Device ID & Unique Scan ID Generators
function getOrCreateDeviceId() {
    let devId = localStorage.getItem('attendance_device_id');
    if (!devId) {
        devId = 'dev_' + (window.crypto && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36));
        localStorage.setItem('attendance_device_id', devId);
    }
    return devId;
}

function generateScanId() {
    return 'scan_' + (window.crypto && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36));
}

function getLocalDateString() {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Global State
const state = {
    activeTab: 'dashboard',
    streams: {
        registration: null,
        kiosk: null
    },
    kioskScanning: false,
    kioskInterval: null,
    kioskProcessing: false,
    kioskMode: 'check_in', // Added kiosk mode state
    requireConfidence60: localStorage.getItem('attendance-confidence-policy') === 'strict_60',
    registeredStudents: [],
    historyViewMode: 'log'
};

// DOM Elements
const elements = {
    menuItems: document.querySelectorAll('.menu-item'),
    tabs: document.querySelectorAll('.tab-content'),
    pageTitle: document.getElementById('page-title'),
    pageSubtitle: document.getElementById('page-subtitle'),
    currentTime: document.getElementById('current-time'),

    // Stats
    statRegistered: document.getElementById('stat-registered'),
    statPresent: document.getElementById('stat-present'),
    statAbsent: document.getElementById('stat-absent'),
    statRate: document.getElementById('stat-rate'),

    // Dashboard
    liveLogs: document.getElementById('live-logs'),
    campusCount: document.getElementById('campus-count'),
    csvDropZone: document.getElementById('csv-drop-zone'),
    csvFileInput: document.getElementById('csv-file-input'),
    csvUploadStatus: document.getElementById('csv-upload-status'),

    // Registration
    regNoInput: document.getElementById('reg-no'),
    regStatusAlert: document.getElementById('reg-status-alert'),
    startCaptureBtn: document.getElementById('start-capture-btn'),
    resetRegisterBtn: document.getElementById('reset-register-btn'),
    registrationVideo: document.getElementById('registration-video'),
    registrationCanvas: document.getElementById('registration-canvas'),
    countdownOverlay: document.getElementById('countdown-overlay'),
    countdownNumber: document.getElementById('countdown-number'),
    cameraFallbackMsg: document.getElementById('camera-fallback-msg'),
    cameraStatusBadge: document.getElementById('camera-status-badge'),
    regProgressContainer: document.getElementById('reg-progress-container'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    progressPercent: document.getElementById('progress-percent'),
    registrationFeedback: document.getElementById('registration-feedback'),
    framesPreviewGrid: document.getElementById('frames-preview-grid'),

    // Kiosk
    kioskVideo: document.getElementById('kiosk-video'),
    kioskCanvas: document.getElementById('kiosk-canvas'),
    kioskFallbackMsg: document.getElementById('kiosk-fallback-msg'),
    toggleKioskBtn: document.getElementById('toggle-kiosk-btn'),
    kioskStatusStrip: document.getElementById('kiosk-status-strip'),
    kioskResultPanel: document.getElementById('kiosk-result-panel'),
    resultCroppedFace: document.getElementById('result-cropped-face'),
    resultIconPlaceholder: document.getElementById('result-icon-placeholder'),
    resultRegNo: document.getElementById('result-reg-no'),
    resultStatusText: document.getElementById('result-status-text'),
    resultTime: document.getElementById('result-time'),
    resultConfidence: document.getElementById('result-confidence'),
    resultName: document.getElementById('result-name'),
    resultRegNoDetail: document.getElementById('result-reg-no-detail'),
    resultDept: document.getElementById('result-dept'),
    resultShift: document.getElementById('result-shift'),
    confidenceToggle: document.getElementById('confidence-60-toggle'),

    // History
    historyDate: document.getElementById('history-date'),
    exportPdfBtn: document.getElementById('export-pdf-btn'),
    exportExcelBtn: document.getElementById('export-excel-btn'),
    historyTableBody: document.getElementById('history-table-body')
};

// Page Title & Subtitle Mapping
const pageMetadata = {
    dashboard: { title: 'Dashboard', subtitle: 'System status, logs and metrics summary' },
    register: { title: 'Face Registration', subtitle: 'Register first-year student face embeddings' },
    kiosk: { title: 'Kiosk Attendance', subtitle: 'Automatic face recognition check-in/out station' },
    history: { title: 'History & Reports', subtitle: 'Detailed records and PDF generation logs' }
};

// 1. INITIALIZATION & SETUP
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    // Initialize Lucide Icons
    lucide.createIcons();

    // Start Time Widget
    updateTimeWidget();
    setInterval(updateTimeWidget, 1000);

    // Setup Theme Selector
    setupThemeSelector();

    // Setup Tab Navigation
    setupTabNavigation();

    // Setup Camera Access for Register
    setupRegistrationCamera();

    // Setup Kiosk Mode buttons
    setupKioskModeButtons();
    if (elements.confidenceToggle) {
        state.requireConfidence60 = elements.confidenceToggle.checked;
        elements.confidenceToggle.checked = state.requireConfidence60;
        elements.confidenceToggle.addEventListener('change', () => {
            state.requireConfidence60 = elements.confidenceToggle.checked;
            localStorage.setItem(
                'attendance-confidence-policy',
                state.requireConfidence60 ? 'strict_60' : 'standard'
            );
        });
    }

    // Setup History Date & Filter
    if (elements.historyDate) {
        fetch('/api/system/today')
            .then(res => res.json())
            .then(data => {
                if (data.date) elements.historyDate.value = data.date;
                loadHistoryLogs(true);
            })
            .catch(() => {
                elements.historyDate.value = getLocalDateString();
                loadHistoryLogs(true);
            });
        elements.historyDate.addEventListener('change', () => loadHistoryLogs());
    }

    const historyFilter = document.getElementById('history-filter');
    if (historyFilter) historyFilter.addEventListener('change', () => loadHistoryLogs());
    if (elements.exportPdfBtn) elements.exportPdfBtn.addEventListener('click', exportPDF);
    if (elements.exportExcelBtn) elements.exportExcelBtn.addEventListener('click', exportExcel);

    // Live Auto-Refresh for Active Tabs
    setInterval(() => {
        if (state.activeTab === 'history') {
            loadHistoryLogs(true);
        } else if (state.activeTab === 'dashboard' || state.activeTab === 'kiosk') {
            loadDashboardStats(); // Silent background refresh
        }
    }, 3000);



    // Setup History Views
    const viewLogBtn = document.getElementById('view-log-btn');
    const viewReportBtn = document.getElementById('view-report-btn');
    if (viewLogBtn && viewReportBtn) {
        viewLogBtn.addEventListener('click', () => {
            state.historyViewMode = 'log';
            viewLogBtn.classList.add('active');
            viewReportBtn.classList.remove('active');
            loadHistoryLogs();
        });
        viewReportBtn.addEventListener('click', () => {
            state.historyViewMode = 'report';
            viewReportBtn.classList.add('active');
            viewLogBtn.classList.remove('active');
            loadHistoryLogs();
        });
    }

    // Session UI Handlers
    const endSessionBtn = document.getElementById('dashboard-end-session-btn');
    const newSessionBtn = document.getElementById('dashboard-new-session-btn');
    const modal = document.getElementById('password-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalDesc = document.getElementById('modal-desc');
    const modalConfirm = document.getElementById('confirm-session-btn');
    const modalCancel = document.getElementById('cancel-session-btn');
    const pwdInput = document.getElementById('session-password-input');

    let currentModalAction = '';

    if (endSessionBtn) {
        endSessionBtn.addEventListener('click', () => {
            currentModalAction = 'end';
            modalTitle.innerText = 'End Session Authorization';
            modalTitle.style.color = 'var(--color-danger)';
            modalDesc.innerText = 'Please enter the admin password to end the current session. All incomplete check-ins will be marked as absent.';
            modalConfirm.className = 'btn btn-danger';
            modal.style.display = 'flex';
            pwdInput.value = '';
            pwdInput.focus();
        });
    }

    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', () => {
            currentModalAction = 'new';
            modalTitle.innerText = 'Reset Today Session Authorization';
            modalTitle.style.color = 'var(--color-warning)';
            modalDesc.innerText = "Please enter the admin password. This will reset today's check-in/check-out logs and clear all cooldowns so you can start fresh.";
            modalConfirm.className = 'btn btn-warning';
            modal.style.display = 'flex';
        });
    }

    const endS1Btn = document.getElementById('dashboard-end-s1-btn');
    if (endS1Btn) {
        endS1Btn.addEventListener('click', () => {
            currentModalAction = 'end_s1';
            modalTitle.innerText = 'End Session 1 (S1) Authorization';
            modalTitle.style.color = 'var(--color-warning)';
            modalDesc.innerText = 'Please enter the admin password. This will close Session 1. Any student scanning after this will be logged into Session 2 (S2) only.';
            modalConfirm.className = 'btn btn-warning';
            modal.style.display = 'flex';
            pwdInput.value = '';
            pwdInput.focus();
        });
    }

    const forceCheckoutActiveBtn = document.getElementById('dashboard-force-checkout-active-btn');
    if (forceCheckoutActiveBtn) {
        forceCheckoutActiveBtn.addEventListener('click', () => {
            currentModalAction = 'force_checkout_active';
            modalTitle.innerText = 'Force Checkout (Active) Authorization';
            modalTitle.style.color = 'var(--color-warning)';
            modalDesc.innerText = 'Please enter the admin password. This will force check-out all students currently checked in (already on campus) without marking absent students.';
            modalConfirm.className = 'btn btn-warning';
            modal.style.display = 'flex';
            pwdInput.value = '';
            pwdInput.focus();
        });
    }

    if (modalCancel) {
        modalCancel.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }

    if (modalConfirm) {
        modalConfirm.addEventListener('click', async () => {
            const pwd = pwdInput.value;
            let endpoint = '/api/admin/session/new_with_password';
            if (currentModalAction === 'end') {
                endpoint = '/api/admin/session/end_with_password';
            } else if (currentModalAction === 'end_s1') {
                endpoint = '/api/admin/session/end_s1_with_password';
            } else if (currentModalAction === 'force_checkout_active') {
                endpoint = '/api/admin/session/force_checkout_active_with_password';
            }

            try {
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: pwd })
                });
                const data = await res.json();
                if (res.ok) {
                    showToast(data.message, 'toast-success');
                    modal.style.display = 'none';
                    if (state.activeTab === 'dashboard') loadDashboardStats();
                    if (state.activeTab === 'history') loadHistoryLogs();
                } else {
                    showToast(data.detail, 'toast-error');
                }
            } catch (err) {
                showToast('Failed to connect to server', 'toast-error');
            }
        });
    }

    // Setup CSV Drag and Drop Upload Logic
    const dropZone = elements.csvDropZone;
    const fileInput = elements.csvFileInput;
    const uploadStatus = elements.csvUploadStatus;

    if (dropZone && fileInput) {
        // Check if database already has students and update dropzone visual state
        fetch('/api/students')
            .then(res => res.json())
            .then(students => {
                if (students && students.length > 0) {
                    const savedName = localStorage.getItem('loaded_csv_name') || 'students.csv';
                    dropZone.style.background = 'rgba(16, 185, 129, 0.15)';
                    dropZone.style.borderColor = 'var(--color-success)';
                    const iconEl = dropZone.querySelector('[data-lucide]');
                    if (iconEl) {
                        iconEl.setAttribute('data-lucide', 'check-circle2');
                        iconEl.style.color = 'var(--color-success)';
                    }
                    const dropZoneText = dropZone.querySelector('p');
                    if (dropZoneText) {
                        dropZoneText.innerHTML = `<strong>Loaded:</strong> ${savedName}`;
                        dropZoneText.style.color = 'var(--color-success)';
                    }
                    lucide.createIcons();
                } else {
                    localStorage.removeItem('loaded_csv_name');
                }
            })
            .catch(err => console.error("Error checking initial students count:", err));

        // Since fileInput transparently overlays dropZone, all click and drag events hit fileInput directly.
        fileInput.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.background = 'rgba(59, 130, 246, 0.2)';
            dropZone.style.borderColor = 'var(--color-primary)';
        });

        fileInput.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.style.background = 'rgba(0,0,0,0.15)';
            dropZone.style.borderColor = 'var(--border-color)';
        });

        fileInput.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.background = 'rgba(0,0,0,0.15)';
            dropZone.style.borderColor = 'var(--border-color)';

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
            const lowerName = file.name.toLowerCase();
            if (!lowerName.endsWith('.csv') && !lowerName.endsWith('.xls') && !lowerName.endsWith('.xlsx')) {
                showToast('Only CSV or Excel files are allowed', 'toast-error');
                return;
            }

            const dropZoneText = dropZone.querySelector('p');
            const iconEl = dropZone.querySelector('[data-lucide]');
            const originalText = 'Click or Drag & Drop CSV Here';

            // Set dropzone to uploading state visually
            dropZone.style.background = 'rgba(59, 130, 246, 0.15)';
            dropZone.style.borderColor = 'var(--color-primary)';
            if (iconEl) {
                iconEl.setAttribute('data-lucide', 'upload-cloud');
                iconEl.style.color = 'var(--color-primary)';
            }
            if (dropZoneText) {
                dropZoneText.innerText = `Uploading ${file.name}...`;
                dropZoneText.style.color = '';
            }

            uploadStatus.style.display = 'block';
            uploadStatus.style.color = 'var(--color-primary)';
            uploadStatus.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> Uploading ${file.name}...`;
            lucide.createIcons();

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/upload_students_csv', {
                    method: 'POST',
                    body: formData
                });

                const data = await res.json();
                if (res.ok) {
                    localStorage.setItem('loaded_csv_name', file.name);
                    uploadStatus.style.color = 'var(--color-success)';
                    uploadStatus.innerText = `Success! Imported ${data.imported} student records from ${file.name}.`;
                    showToast(`Imported ${data.imported} students`, 'toast-success');

                    // Show green loaded success state on dropzone
                    dropZone.style.background = 'rgba(16, 185, 129, 0.15)';
                    dropZone.style.borderColor = 'var(--color-success)';
                    if (iconEl) {
                        iconEl.setAttribute('data-lucide', 'check-circle2');
                        iconEl.style.color = 'var(--color-success)';
                    }
                    if (dropZoneText) {
                        dropZoneText.innerHTML = `<strong>Loaded:</strong> ${file.name}`;
                        dropZoneText.style.color = 'var(--color-success)';
                    }
                    lucide.createIcons();

                    if (state.activeTab === 'dashboard') loadDashboardStats();
                    if (state.activeTab === 'history') loadHistoryLogs();
                } else {
                    uploadStatus.style.color = 'var(--color-danger)';
                    uploadStatus.innerText = `Error: ${data.detail || 'Upload failed'}`;
                    showToast(data.detail || 'Upload failed', 'toast-error');

                    // Reset to original styling on failure
                    dropZone.style.background = 'rgba(0,0,0,0.15)';
                    dropZone.style.borderColor = 'var(--border-color)';
                    if (iconEl) {
                        iconEl.setAttribute('data-lucide', 'upload-cloud');
                        iconEl.style.color = 'var(--color-primary)';
                    }
                    if (dropZoneText) {
                        dropZoneText.innerText = originalText;
                        dropZoneText.style.color = '';
                    }
                    lucide.createIcons();
                }
            } catch (err) {
                uploadStatus.style.color = 'var(--color-danger)';
                uploadStatus.innerText = 'Network error during upload.';
                showToast('Network error during upload', 'toast-error');

                // Reset to original styling on network error
                dropZone.style.background = 'rgba(0,0,0,0.15)';
                dropZone.style.borderColor = 'var(--border-color)';
                if (iconEl) {
                    iconEl.setAttribute('data-lucide', 'upload-cloud');
                    iconEl.style.color = 'var(--color-primary)';
                }
                if (dropZoneText) {
                    dropZoneText.innerText = originalText;
                    dropZoneText.style.color = '';
                }
                lucide.createIcons();
            }

            fileInput.value = '';
        }
    }

    if (path === '/face-registration') {
        document.body.classList.add('fullscreen-mode');
        setTimeout(() => switchTab('register'), 100);
    } else if (path === '/face-attendance') {
        document.body.classList.add('fullscreen-mode');
        setTimeout(() => switchTab('kiosk'), 100);
    } else {
        // Load Initial Data
        loadDashboardStats();
    }
});

// Update Clock
function updateTimeWidget() {
    if (!elements.currentTime) return;
    const now = new Date();
    elements.currentTime.innerText = now.toLocaleTimeString();
}
// 1.5 THEME SELECTOR LOGIC
function setupThemeSelector() {
    const themeSelector = document.getElementById('theme-selector');
    if (!themeSelector) return;

    // Load from local storage
    const savedTheme = localStorage.getItem('app-theme') || 'theme-nordic';
    if (savedTheme === 'default') {
        document.body.className = '';
    } else {
        document.body.className = savedTheme;
    }
    themeSelector.value = savedTheme;

    themeSelector.addEventListener('change', (e) => {
        const theme = e.target.value;
        if (theme === 'default') {
            document.body.className = '';
        } else {
            document.body.className = theme;
        }
        localStorage.setItem('app-theme', theme);
    });
}

// 2. TAB NAVIGATION
function setupTabNavigation() {
    elements.menuItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = item.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    if (state.activeTab === tabName) return;

    // Stop active camera feeds
    stopAllCameras();

    // Toggle active classes on menu
    elements.menuItems.forEach(item => {
        if (item.getAttribute('data-tab') === tabName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Toggle active classes on content panels
    elements.tabs.forEach(tab => {
        if (tab.id === `tab-${tabName}`) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Update Header Metadata
    if (elements.pageTitle && elements.pageSubtitle) {
        const meta = pageMetadata[tabName];
        if (meta) {
            elements.pageTitle.innerText = meta.title;
            elements.pageSubtitle.innerText = meta.subtitle;
        }
    }

    state.activeTab = tabName;

    // Tab Specific Actions
    if (tabName === 'dashboard') {
        loadDashboardStats();
    } else if (tabName === 'register') {
        startRegistrationCamera();
    } else if (tabName === 'kiosk') {
        startKioskCamera();
    } else if (tabName === 'history') {
        loadHistoryLogs();
    }
}

// 3. CAMERA UTILITIES
async function startCamera(videoElement, fallbackElement) {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: 'user' // Front camera for kiosk/registration
            },
            audio: false
        });

        videoElement.srcObject = stream;
        videoElement.style.display = 'block';
        if (fallbackElement) fallbackElement.style.display = 'none';
        return stream;
    } catch (err) {
        console.error("Camera Access Error: ", err);
        videoElement.style.display = 'none';
        if (fallbackElement) fallbackElement.style.display = 'flex';
        return null;
    }
}

function stopAllCameras() {
    // Stop registration camera
    if (state.streams.registration) {
        state.streams.registration.getTracks().forEach(track => track.stop());
        state.streams.registration = null;
        elements.registrationVideo.srcObject = null;
    }

    // Stop kiosk camera
    if (state.streams.kiosk) {
        state.streams.kiosk.getTracks().forEach(track => track.stop());
        state.streams.kiosk = null;
        elements.kioskVideo.srcObject = null;
    }

    // Stop kiosk scanning loop
    if (state.kioskScanning) {
        toggleKioskScanning(false);
    }

    // Stop barcode scanner
    if (state.html5QrCode) {
        state.html5QrCode.stop().then(() => {
            state.html5QrCode = null;
        }).catch(err => {
            console.warn("Error stopping barcode scanner:", err);
            state.html5QrCode = null;
        });
    }
}

// 4. DASHBOARD LOGIC
async function loadDashboardStats() {
    try {
        // Fetch today's logs directly from server
        const logsRes = await fetch('/api/attendance');
        const logs = await logsRes.json();

        // Fetch students
        const studentsRes = await fetch('/api/students');
        const students = await studentsRes.json();

        const totalRegistered = students.length;
        // Count student as present if they have checked in or completed session
        const present = logs.filter(log => log.s1_in || log.s2_in || log.status === 'PRESENT').length;
        const absent = Math.max(0, totalRegistered - present);
        const rate = totalRegistered > 0 ? (present / totalRegistered) : 0;

        // Update elements
        elements.statRegistered.innerText = totalRegistered;
        elements.statPresent.innerText = present;
        elements.statAbsent.innerText = absent;
        elements.statRate.innerText = `${Math.round(rate * 100)}%`;

        // Update SVG Progress Rings
        const updateRing = (id, percentage) => {
            const ring = document.getElementById(id);
            if (ring) {
                const offset = 125.6 - (125.6 * percentage);
                ring.style.strokeDashoffset = offset;
            }
        };

        updateRing('ring-present', totalRegistered > 0 ? present / totalRegistered : 0);
        updateRing('ring-absent', totalRegistered > 0 ? absent / totalRegistered : 0);
        updateRing('ring-rate', rate);

        // Fetch System Health
        try {
            const healthRes = await fetch('/api/system/health');
            const health = await healthRes.json();
            const cooldownEl = document.getElementById('health-cooldown');
            if (cooldownEl) cooldownEl.innerText = health.cooldown_count;
        } catch (e) {
            console.error("Health fetch failed", e);
        }

        // Determine the latest state for each student
        logs.forEach(log => {
            let lastAction = null;
            if (log.s2_out) { lastAction = 'out'; }
            else if (log.s2_in) { lastAction = 'in'; }
            else if (log.s1_out && log.s1_out !== 'SKIPPED') { lastAction = 'out'; }
            else if (log.s1_in) { lastAction = 'in'; }
            log._lastAction = lastAction;
        });

        // Populate Recent Activity Timeline
        elements.liveLogs.innerHTML = '';

        // Extract all individual scan events across all users
        let allScanEvents = [];
        logs.forEach(log => {
            if (log.s1_in) allScanEvents.push({ reg_no: log.reg_no, action: 'Check-In', time: log.s1_in, type: 'in' });
            if (log.s1_out) allScanEvents.push({ reg_no: log.reg_no, action: 'Check-Out', time: log.s1_out, type: 'out' });
            if (log.s2_in) allScanEvents.push({ reg_no: log.reg_no, action: 'Check-In', time: log.s2_in, type: 'in' });
            if (log.s2_out) allScanEvents.push({ reg_no: log.reg_no, action: 'Check-Out', time: log.s2_out, type: 'out' });
        });

        // Sort descending by time
        allScanEvents.sort((a, b) => b.time.localeCompare(a.time));

        if (allScanEvents.length === 0) {
            elements.liveLogs.innerHTML = '<div class="no-logs">No scans recorded today yet.</div>';
        } else {
            allScanEvents.forEach(event => {
                const item = document.createElement('div');
                item.className = 'log-item';
                item.innerHTML = `
                    <div class="log-info">
                        <span class="log-status-dot ${event.type}"></span>
                        <div class="log-details">
                            <span class="log-reg">${event.reg_no}</span>
                            <span class="log-meta">${event.action}</span>
                        </div>
                    </div>
                    <div class="log-time-box">
                        <span class="log-time">${event.time}</span>
                    </div>
                `;
                elements.liveLogs.appendChild(item);
            });
        }

        // Populate Live Campus Roster
        const campusRoster = document.getElementById('campus-roster');
        if (campusRoster) {
            campusRoster.innerHTML = '';
            const onCampus = logs.filter(log => log._lastAction === 'in');

            if (elements.campusCount) {
                elements.campusCount.innerText = `${onCampus.length}`;
            }

            if (onCampus.length === 0) {
                campusRoster.innerHTML = '<div class="no-logs">Campus is empty.</div>';
            } else {
                onCampus.forEach(log => {
                    // find latest check in time
                    let inTime = log.s2_in || log.s1_in;
                    const item = document.createElement('div');
                    item.className = 'log-item';
                    item.innerHTML = `
                        <div class="log-info">
                            <span class="log-status-dot in" style="box-shadow: 0 0 8px var(--color-success);"></span>
                            <div class="log-details">
                                <span class="log-reg" style="font-size: 14px;">${log.reg_no}</span>
                                <span class="log-meta text-success">Inside</span>
                            </div>
                        </div>
                        <div class="log-time-box">
                            <span class="log-time">${inTime}</span>
                        </div>
                    `;
                    campusRoster.appendChild(item);
                });
            }
        }
    } catch (err) {
        console.error("Error loading stats:", err);
    }
}

// 5. REGISTRATION LOGIC
async function setupRegistrationCamera() {
    if (!elements.regNoInput) return;

    async function checkStudentStatus(val) {
        if (!val || val.length < 4) return;
        try {
            // Auto lookup student details
            const userInfoRes = await fetch(`/api/user_info/${val}`);
            const userInfoData = await userInfoRes.json();

            if (userInfoData.status === 'success' && userInfoData.data) {
                const s = userInfoData.data;
                const nameInput = document.getElementById('reg-name');
                const deptInput = document.getElementById('reg-dept');
                const phoneInput = document.getElementById('reg-phone');
                const shiftInput = document.getElementById('reg-shift');

                if (nameInput && s.name) nameInput.value = s.name;
                if (deptInput && s.department) deptInput.value = s.department;
                if (phoneInput && s.phone) phoneInput.value = s.phone;
                if (shiftInput && (s.shift || s.email)) shiftInput.value = s.shift || s.email;

                showToast(`Loaded details for ${val}`, 'toast-info');

                const date = getLocalDateString();
                const logsRes = await fetch(`/api/attendance?date=${date}`);
                const logs = await logsRes.json();

                const studentLog = logs.find(log => log.reg_no === val);
                if (studentLog) {
                    studentLog.check_in_time = studentLog.s1_in || studentLog.s2_in || null;
                    studentLog.check_out_time = studentLog.s2_out || studentLog.s1_out || null;
                    const isCheckIn = studentLog.check_out_time === null;
                    const statusText = isCheckIn ? 'Checked In' : 'Checked Out';
                    const time = studentLog.check_out_time || studentLog.check_in_time;
                    showFeedback(
                        elements.regStatusAlert,
                        `Note: Student <b>${val}</b> is currently <b>${statusText}</b> (at ${time}).`,
                        isCheckIn ? 'success' : 'warning'
                    );
                } else {
                    elements.regStatusAlert.style.display = 'none';
                }
            }
        } catch (e) {
            console.error("Error checking student status:", e);
        }
    }

    // Listener for Registration Form Input
    elements.regNoInput.addEventListener('input', () => {
        const val = elements.regNoInput.value.trim().toUpperCase();
        elements.startCaptureBtn.disabled = val.length === 0 || !state.streams.registration;
        elements.regStatusAlert.style.display = 'none';
        checkStudentStatus(val);
    });

    // Check status on blur
    elements.regNoInput.addEventListener('blur', () => {
        const val = elements.regNoInput.value.trim().toUpperCase();
        checkStudentStatus(val);
    });

    // Check status on Enter keydown
    elements.regNoInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const val = elements.regNoInput.value.trim().toUpperCase();
            checkStudentStatus(val);
        }
    });

    // Reset button
    elements.resetRegisterBtn.addEventListener('click', () => {
        elements.regNoInput.value = '';
        elements.startCaptureBtn.disabled = true;
        elements.regProgressContainer.style.display = 'none';
        elements.registrationFeedback.style.display = 'none';
        elements.regStatusAlert.style.display = 'none';
        elements.framesPreviewGrid.innerHTML = `
            <div class="frame-placeholder"></div>
            <div class="frame-placeholder"></div>
            <div class="frame-placeholder"></div>
            <div class="frame-placeholder"></div>
            <div class="frame-placeholder"></div>
        `;
    });

    // Start Capture button click
    elements.startCaptureBtn.addEventListener('click', startFaceCaptureFlow);
}

async function startRegistrationCamera() {
    elements.cameraStatusBadge.innerText = "Connecting...";
    elements.cameraStatusBadge.className = "badge";

    const stream = await startCamera(elements.registrationVideo, elements.cameraFallbackMsg);

    if (stream) {
        state.streams.registration = stream;
        elements.cameraStatusBadge.innerText = "Connected";
        elements.cameraStatusBadge.className = "badge badge-pulse";

        // Re-evaluate button state
        const val = elements.regNoInput.value.trim();
        elements.startCaptureBtn.disabled = val.length === 0;
    } else {
        elements.cameraStatusBadge.innerText = "Disabled";
        elements.cameraStatusBadge.className = "badge";
        elements.startCaptureBtn.disabled = true;
    }
}

async function startFaceCaptureFlow() {
    const regNo = elements.regNoInput.value.trim().toUpperCase();
    if (!regNo) return;

    // Lock inputs
    elements.regNoInput.disabled = true;
    elements.startCaptureBtn.disabled = true;
    elements.resetRegisterBtn.disabled = true;

    elements.registrationFeedback.style.display = 'none';
    elements.framesPreviewGrid.innerHTML = '';

    // Start Countdown
    elements.countdownOverlay.style.display = 'flex';
    elements.regProgressContainer.style.display = 'block';

    let countdownVal = 6;
    elements.countdownNumber.innerText = countdownVal;

    // Prepare frame collection
    const capturedImages = [];
    const maxCaptures = 10;
    const captureInterval = 600; // Capture every 600ms (6 seconds total)
    let captureCount = 0;

    // Countdown Timer (1s ticks)
    const countdownTimer = setInterval(() => {
        countdownVal--;
        elements.countdownNumber.innerText = countdownVal;
        if (countdownVal <= 0) {
            clearInterval(countdownTimer);
            elements.countdownOverlay.style.display = 'none';
        }
    }, 1000);

    // Capture Timer
    const captureTimer = setInterval(() => {
        captureCount++;

        // Draw frame to offscreen canvas
        const video = elements.registrationVideo;
        const canvas = elements.registrationCanvas;
        const ctx = canvas.getContext('2d');

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;

        // Draw flipped image to canvas to match visual mirror
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform

        // Get Base64 image data
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        capturedImages.push(dataUrl);

        // Add preview thumbnail
        const thumb = document.createElement('img');
        thumb.src = dataUrl;
        thumb.className = 'frame-thumb';

        // Remove dummy placeholder if exists
        if (elements.framesPreviewGrid.children.length >= maxCaptures) {
            elements.framesPreviewGrid.removeChild(elements.framesPreviewGrid.firstChild);
        }
        elements.framesPreviewGrid.appendChild(thumb);

        // Update Progress Bar
        const percent = Math.round((captureCount / maxCaptures) * 100);
        elements.progressBarFill.style.width = `${percent}%`;
        elements.progressPercent.innerText = `${percent}%`;

        if (captureCount >= maxCaptures) {
            clearInterval(captureTimer);
            submitRegistration(regNo, capturedImages);
        }
    }, captureInterval);
}

async function submitRegistration(regNo, images) {
    showFeedback(elements.registrationFeedback, "Analyzing faces and generating embeddings...", "info");

    const name = document.getElementById('reg-name') ? document.getElementById('reg-name').value.trim() : "";
    const department = document.getElementById('reg-dept') ? document.getElementById('reg-dept').value.trim() : "";
    const phone = document.getElementById('reg-phone') ? document.getElementById('reg-phone').value.trim() : "";
    const shift = document.getElementById('reg-shift') ? document.getElementById('reg-shift').value : "Shift 1";

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reg_no: regNo,
                images: images,
                name: name,
                department: department,
                phone: phone,
                shift: shift,
                email: shift,
                device_id: getOrCreateDeviceId(),
                scan_id: generateScanId()
            })
        });

        const data = await res.json();

        if (res.ok) {
            showFeedback(
                elements.registrationFeedback,
                `Successfully registered student <b>${regNo}</b> and checked in. Processed ${data.frames_successful}/${data.frames_processed} high-quality frames.`,
                "success"
            );
            showToast(`User ${regNo} registered & checked in!`, 'toast-success');
            loadDashboardStats();
            loadHistoryLogs(true);
        } else {
            showFeedback(elements.registrationFeedback, data.detail || "Failed to register.", "error");
        }
    } catch (err) {
        showFeedback(elements.registrationFeedback, "Server error during registration.", "error");
    } finally {
        // Unlock inputs
        elements.regNoInput.disabled = false;
        elements.startCaptureBtn.disabled = false;
        elements.resetRegisterBtn.disabled = false;
    }
}

// 6. KIOSK (FACE ATTENDANCE) LOGIC
async function startKioskCamera() {
    const stream = await startCamera(elements.kioskVideo, elements.kioskFallbackMsg);
    if (stream) {
        state.streams.kiosk = stream;
    } else {
        elements.toggleKioskBtn.disabled = true;
    }
}

// Toggle Scanning button
if (elements.toggleKioskBtn) {
    elements.toggleKioskBtn.addEventListener('click', () => {
        if (state.kioskScanning) {
            toggleKioskScanning(false);
        } else {
            toggleKioskScanning(true);
        }
    });
}

function toggleKioskScanning(start) {
    if (start) {
        state.kioskScanning = true;
        elements.toggleKioskBtn.className = "btn btn-sm btn-danger";
        elements.toggleKioskBtn.innerHTML = '<i data-lucide="square"></i><span>Stop Scanning</span>';
        const modeLabel = state.kioskMode === 'check_in' ? 'Check-In Only' : 'Check-Out Only';
        elements.kioskStatusStrip.innerText = `Kiosk Scanning (${modeLabel})... Hold face in box.`;
        elements.kioskStatusStrip.className = "kiosk-status-strip active";

        // Start Interval Loop (Every 1.5 seconds)
        state.kioskInterval = setInterval(captureKioskFace, 1500);
    } else {
        state.kioskScanning = false;
        elements.toggleKioskBtn.className = "btn btn-sm btn-success";
        elements.toggleKioskBtn.innerHTML = '<i data-lucide="play"></i><span>Start Scanning</span>';
        elements.kioskStatusStrip.innerText = "Kiosk Idle";
        elements.kioskStatusStrip.className = "kiosk-status-strip";

        if (state.kioskInterval) {
            clearInterval(state.kioskInterval);
            state.kioskInterval = null;
        }
    }
    lucide.createIcons();
}

function setupKioskModeButtons() {
    const checkinBtn = document.getElementById('mode-checkin-btn');
    const checkoutBtn = document.getElementById('mode-checkout-btn');

    if (checkinBtn && checkoutBtn) {
        checkinBtn.addEventListener('click', () => {
            state.kioskMode = 'check_in';
            checkinBtn.classList.add('active');
            checkoutBtn.classList.remove('active');
            if (state.kioskScanning) {
                elements.kioskStatusStrip.innerText = "Kiosk Scanning (Check-In Only)... Hold face in box.";
            }
        });

        checkoutBtn.addEventListener('click', () => {
            state.kioskMode = 'check_out';
            checkoutBtn.classList.add('active');
            checkinBtn.classList.remove('active');
            if (state.kioskScanning) {
                elements.kioskStatusStrip.innerText = "Kiosk Scanning (Check-Out Only)... Hold face in box.";
            }
        });
    }
}

async function captureKioskFace() {
    if (!state.streams.kiosk || state.kioskProcessing) return;

    state.kioskProcessing = true;

    const video = elements.kioskVideo;
    const canvas = elements.kioskCanvas;
    const ctx = canvas.getContext('2d');

    const captureFrame = () => {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        return canvas.toDataURL('image/jpeg', 0.85);
    };

    const dataUrl = captureFrame();

    const currentDeviceId = getOrCreateDeviceId();
    const currentScanId = generateScanId();

    elements.kioskStatusStrip.innerText = "Analyzing camera frame...";

    try {
        const res = await fetch('/api/attendance/face', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: dataUrl,
                mode: state.kioskMode,
                require_confidence_60: state.requireConfidence60,
                device_id: currentDeviceId,
                scan_id: currentScanId
            })
        });

        const data = await res.json();

        // Enforce device isolation: verify response matches local scan_id / device_id
        if (data.scan_id && data.scan_id !== currentScanId) {
            console.warn(`[Isolation] Mismatched scan_id received: expected ${currentScanId}, got ${data.scan_id}`);
            return;
        }

        if (res.ok) {
            // Update UI with student details
            elements.kioskResultPanel.className = "result-display-panel";

            let currentData = data;

            if (currentData.data.status === 'needs_confirmation') {
                playBeep(440);

                // Hide normal details
                const detailsBox = document.getElementById('result-details-box');
                detailsBox.style.display = 'none';

                // Show inline warning in the kiosk-result-panel
                elements.kioskResultPanel.className = "result-display-panel warning-glow";
                elements.resultStatusText.innerText = 'ATTENTION REQUIRED';
                elements.resultStatusText.style.color = 'var(--color-warning)';

                // Remove any existing warning box to prevent duplicates
                const existingBox = document.getElementById('inline-warning-box');
                if (existingBox) existingBox.remove();

                // Create warning box inline
                const warningBox = document.createElement('div');
                warningBox.id = 'inline-warning-box';
                warningBox.innerHTML = `
                    <div style="padding: 15px; background: rgba(234, 179, 8, 0.1); border-radius: 8px; border: 1px solid rgba(234, 179, 8, 0.3); margin-top: 15px; text-align: center;">
                        <i data-lucide="alert-triangle" style="color: var(--color-warning); width: 32px; height: 32px; margin-bottom: 10px;"></i>
                        <p style="color: var(--color-warning); font-weight: 600; margin-bottom: 5px;">Attention Required!</p>
                        <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 15px;"><strong>${currentData.data.name}</strong>: ${currentData.data.message || 'Previous session check-out was skipped. Force check-in?'}</p>
                        <div style="display: flex; gap: 10px; justify-content: center;">
                            <button id="inline-cancel-btn" class="btn btn-secondary btn-sm" style="flex: 1;">Cancel</button>
                            <button id="inline-confirm-btn" class="btn btn-warning btn-sm" style="flex: 1;">Force Check-In</button>
                        </div>
                    </div>
                `;
                detailsBox.parentNode.insertBefore(warningBox, detailsBox.nextSibling);
                if (window.lucide) lucide.createIcons();

                const userConfirmed = await new Promise((resolve) => {
                    document.getElementById('inline-confirm-btn').addEventListener('click', () => resolve(true));
                    document.getElementById('inline-cancel-btn').addEventListener('click', () => resolve(false));
                });

                warningBox.remove();

                if (userConfirmed) {
                    elements.kioskStatusStrip.innerText = "Confirming check-in...";
                    const confirmRes = await fetch('/api/attendance/face', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            image: dataUrl,
                            mode: state.kioskMode,
                            require_confidence_60: state.requireConfidence60,
                            confirm: true
                        })
                    });
                    const confirmData = await confirmRes.json();
                    if (confirmRes.ok) {
                        currentData = confirmData;
                        detailsBox.style.display = 'block';
                        elements.resultStatusText.style.color = '';
                    } else {
                        elements.kioskResultPanel.classList.add('warning-glow');
                        elements.resultStatusText.innerText = 'ERROR';
                        showToast(confirmData.detail || "Error confirming.", "toast-error");
                        isProcessingFace = false;
                        setTimeout(captureKioskFace, 2000);
                        return;
                    }
                } else {
                    detailsBox.style.display = 'block';
                    elements.resultStatusText.style.color = '';
                    elements.kioskResultPanel.className = "result-display-panel idle";
                    elements.resultStatusText.innerText = 'CANCELLED';
                    showToast("Check-in cancelled.", "toast-warning");
                    isProcessingFace = false;
                    setTimeout(captureKioskFace, 2000);
                    return;
                }
            }

            const status = currentData.data ? currentData.data.status : '';
            const isCheckIn = status === 'check_in';
            const isCheckOut = status === 'check_out';
            const isAlreadyIn = status === 'already_checked_in';
            const isAlreadyOut = status === 'already_checked_out' || status === 'already_completed';
            const isSessionEnded = status === 'session_ended';

            if (isSessionEnded) {
                elements.kioskResultPanel.classList.add('warning-glow');
                elements.resultStatusText.innerText = 'SESSION ENDED';
                playBeep(440);
                showToast(`Session for today has ended. Cannot scan.`, 'toast-error');
            } else if (isCheckIn) {
                elements.kioskResultPanel.classList.add('success-glow');
                elements.resultStatusText.innerText = 'CHECKED IN';
                playBeep(880);
                showToast(`Student ${currentData.reg_no} Checked In`, 'toast-success');
                loadDashboardStats();
                loadHistoryLogs(true);
            } else if (isCheckOut) {
                elements.kioskResultPanel.classList.add('success-glow');
                elements.resultStatusText.innerText = 'CHECKED OUT';
                playBeep(440);
                showToast(`Student ${currentData.reg_no} Checked Out`, 'toast-info');
                loadDashboardStats();
                loadHistoryLogs(true);
            } else if (isAlreadyIn) {
                elements.kioskResultPanel.classList.add('warning-glow');
                elements.resultStatusText.innerText = 'ALREADY IN';
                playBeep(660);
                showToast(`Student ${currentData.reg_no} Already Checked In`, 'toast-warning');
            } else if (isAlreadyOut) {
                elements.kioskResultPanel.classList.add('warning-glow');
                elements.resultStatusText.innerText = 'ALREADY OUT';
                playBeep(660);
                showToast(`Student ${currentData.reg_no} Already Checked Out`, 'toast-warning');
            } else {
                elements.kioskResultPanel.classList.add('warning-glow');
                elements.resultStatusText.innerText = status ? status.toUpperCase().replace('_', ' ') : 'LOGGED';
                playBeep(440);
                showToast(`Student ${currentData.reg_no}: ${status}`, 'toast-info');
            }

            elements.resultIconPlaceholder.style.display = 'none';
            elements.resultCroppedFace.style.display = 'block';

            // Render cropped face returned from backend if available
            if (currentData.face_image) {
                elements.resultCroppedFace.src = `data:image/jpeg;base64,${currentData.face_image}`;
            } else {
                // If not sent by backend, show raw capture drawn to canvas
                const faceCtx = elements.resultCroppedFace.getContext('2d');
                elements.resultCroppedFace.width = 100;
                elements.resultCroppedFace.height = 100;
                // Draw a centered cropped circle from main canvas
                faceCtx.drawImage(canvas, (canvas.width - 200) / 2, (canvas.height - 200) / 2, 200, 200, 0, 0, 100, 100);
            }

            elements.resultRegNo.innerText = currentData.reg_no;
            elements.resultTime.innerText = currentData.server_time || displayCurrentTime();
            elements.resultConfidence.innerText = `${Math.round(currentData.confidence * 100)}%`;

            if (elements.resultName) elements.resultName.innerText = currentData.data.name || '-';
            if (elements.resultRegNoDetail) elements.resultRegNoDetail.innerText = currentData.reg_no || '-';
            if (elements.resultDept) elements.resultDept.innerText = currentData.data.department || '-';
            if (elements.resultShift) elements.resultShift.innerText = currentData.data.shift || currentData.data.email || 'Shift 1';

            if (isAlreadyIn) {
                elements.kioskStatusStrip.innerText = `${currentData.reg_no} is already checked in.`;
            } else {
                elements.kioskStatusStrip.innerText = `Recognized ${currentData.reg_no}!`;
            }

            // Reset status text after 2.5 seconds
            setTimeout(() => {
                if (state.kioskScanning) {
                    const modeLabel = state.kioskMode === 'check_in' ? 'Check-In Only' : 'Check-Out Only';
                    elements.kioskStatusStrip.innerText = `Kiosk Scanning (${modeLabel})... Hold face in box.`;
                }
            }, 2500);
        } else {
            // Handle face not recognized or no face detected
            if (data.detail && data.detail.includes("Face not recognized")) {
                elements.kioskStatusStrip.innerText = "Face not recognized. Try again.";
            } else if (data.detail && data.detail.includes("No face detected")) {
                // Keep looking
            } else {
                elements.kioskStatusStrip.innerText = data.detail || "Scanning error.";
            }
        }
    } catch (err) {
        console.error("Kiosk scanning error:", err);
        elements.kioskStatusStrip.innerText = "Network connection issue.";
    } finally {
        state.kioskProcessing = false;
    }
}

// Play synth sound for attendance logging confirmation
function playBeep(frequency) {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;
        gainNode.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.2);

        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.2);
    } catch (e) {
        // AudioContext not allowed or not supported
    }
}

// 8. HISTORY LOGS & EXPORTS
async function loadHistoryLogs(silent = false) {
    const selectedDate = elements.historyDate.value;
    if (!selectedDate) return;

    if (!silent) {
        elements.historyTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary">Loading logs...</td></tr>';
    }

    try {
        // Fetch Attendance logs for date
        const attRes = await fetch(`/api/attendance?date=${selectedDate}`);
        const attendanceLogs = await attRes.json();

        // Fetch Registered Students
        const studentsRes = await fetch('/api/students');
        const students = await studentsRes.json();

        // Build a combined list of students from /api/students + any attendance logs
        const studentMap = {};
        students.forEach(s => {
            const key = (s.reg_no || '').trim().toUpperCase();
            if (key) {
                studentMap[key] = {
                    reg_no: key,
                    name: s.name || '',
                    department: s.department || '',
                    phone: s.phone || '',
                    shift: s.shift || s.email || 'Shift 1'
                };
            }
        });

        const logMap = {};
        attendanceLogs.forEach(log => {
            const key = (log.reg_no || '').trim().toUpperCase();
            if (key) {
                logMap[key] = log;
                if (!studentMap[key]) {
                    studentMap[key] = {
                        reg_no: key,
                        name: log.name || '',
                        department: log.department || '',
                        phone: log.phone || '',
                        shift: log.email || 'Shift 1'
                    };
                }
            }
        });

        const allStudents = Object.values(studentMap);

        // Populate table
        elements.historyTableBody.innerHTML = '';

        if (allStudents.length === 0) {
            elements.historyTableBody.innerHTML = '<tr><td colspan="10" class="text-center text-secondary">No records found for this date.</td></tr>';
            return;
        }

        // Filter students
        const filterVal = document.getElementById('history-filter') ? document.getElementById('history-filter').value : 'all';
        let displayStudents = allStudents.filter(student => {
            const key = student.reg_no.trim().toUpperCase();
            const log = logMap[key];
            const isPresent = Boolean(log && (log.s1_in || log.s2_in || log.status === 'PRESENT'));
            if (filterVal === 'present') return isPresent;
            if (filterVal === 'absent') return !isPresent;
            return true;
        });

        // Sort students by reg_no
        displayStudents.sort((a, b) => a.reg_no.localeCompare(b.reg_no));

        const thead = document.getElementById('history-table-head');

        if (displayStudents.length === 0) {
            thead.innerHTML = '';
            elements.historyTableBody.innerHTML = '<tr><td colspan="10" class="text-center text-secondary">No records match the selected filter.</td></tr>';
            return;
        }

        if (state.historyViewMode === 'log') {
            thead.innerHTML = `
                <tr>
                    <th>Reg No</th>
                    <th>Name</th>
                    <th>Department</th>
                    <th>Shift</th>
                    <th>S1 In</th>
                    <th>S1 Out</th>
                    <th>S2 In</th>
                    <th>S2 Out</th>
                    <th>Sessions</th>
                    <th>Status</th>
                </tr>
            `;
            displayStudents.forEach((student, index) => {
                const key = student.reg_no.trim().toUpperCase();
                const log = logMap[key];
                const tr = document.createElement('tr');
                let statusClass = 'text-secondary';
                let statusText = 'Not Attended';

                let s1Attended = log && log.s1_in && log.s1_out;
                let s2Attended = log && log.s2_in && log.s2_out;

                let s1Circle = `<span title="Session 1" style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${s1Attended ? 'var(--color-success)' : 'var(--color-danger)'}; margin-right:4px;"></span>`;
                let s2Circle = `<span title="Session 2" style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${s2Attended ? 'var(--color-success)' : 'var(--color-danger)'}; margin-right:4px;"></span>`;

                if (log && log.status) {
                    statusText = log.status;
                    if (log.status === 'PRESENT') {
                        statusClass = 'text-success';
                    } else if (log.status === 'INCOMPLETE') {
                        statusClass = 'text-warning';
                    } else if (log.status.includes('ABSENT')) {
                        statusClass = 'text-danger';
                    }
                } else if (log) {
                    statusClass = 'text-warning';
                    statusText = 'INCOMPLETE';
                }

                const shiftVal = student.shift || (log && log.email ? log.email : 'Shift 1');
                tr.innerHTML = `
                    <td><strong>${student.reg_no}</strong></td>
                    <td>${student.name || '-'}</td>
                    <td>${student.department || '-'}</td>
                    <td><span class="badge" style="background: rgba(37, 99, 235, 0.1); color: var(--color-primary); font-weight: 600;">${shiftVal}</span></td>
                    <td>${log && log.s1_in ? log.s1_in : '-'}</td>
                    <td>${log && log.s1_out ? log.s1_out : '-'}</td>
                    <td>${log && log.s2_in ? log.s2_in : '-'}</td>
                    <td>${log && log.s2_out ? log.s2_out : '-'}</td>
                    <td>${s1Circle}${s2Circle}</td>
                    <td><span class="badge ${statusClass}">${statusText}</span></td>
                `;
                elements.historyTableBody.appendChild(tr);
            });
        } else {
            thead.innerHTML = `
                <tr>
                    <th>S.No</th>
                    <th>Name</th>
                    <th>Reg No</th>
                    <th>Department</th>
                    <th>Phone Number</th>
                    <th>Shift</th>
                    <th>Sessions</th>
                    <th>Status</th>
                </tr>
            `;
            displayStudents.forEach((student, index) => {
                const key = student.reg_no.trim().toUpperCase();
                const log = logMap[key];
                let statusClass = 'text-secondary';
                let statusText = 'Not Attended';

                let s1Attended = log && log.s1_in && log.s1_out;
                let s2Attended = log && log.s2_in && log.s2_out;

                let s1Circle = `<span title="Session 1" style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${s1Attended ? 'var(--color-success)' : 'var(--color-danger)'}; margin-right:4px;"></span>`;
                let s2Circle = `<span title="Session 2" style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${s2Attended ? 'var(--color-success)' : 'var(--color-danger)'}; margin-right:4px;"></span>`;

                if (log && log.status) {
                    statusText = log.status;
                    if (log.status === 'PRESENT') {
                        statusClass = 'text-success';
                    } else if (log.status === 'INCOMPLETE') {
                        statusClass = 'text-warning';
                    } else if (log.status.includes('ABSENT')) {
                        statusClass = 'text-danger';
                    }
                } else if (log) {
                    statusClass = 'text-warning';
                    statusText = 'INCOMPLETE';
                }

                const shiftVal = student.shift || (log && log.email ? log.email : 'Shift 1');
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${index + 1}</td>
                    <td><strong>${student.name || '-'}</strong></td>
                    <td>${student.reg_no}</td>
                    <td>${student.department || '-'}</td>
                    <td>${student.phone || '-'}</td>
                    <td><span class="badge" style="background: rgba(37, 99, 235, 0.1); color: var(--color-primary); font-weight: 600;">${shiftVal}</span></td>
                    <td>${s1Circle}${s2Circle}</td>
                    <td><span class="badge ${statusClass}">${statusText}</span></td>
                `;
                elements.historyTableBody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error("Failed to load history", err);
        elements.historyTableBody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Failed to fetch logs.</td></tr>';
    }
}

async function confirmDeleteStudent(regNo) {
    if (!confirm(`Are you sure you want to delete student ${regNo}? This will remove all their face embeddings and their entire attendance history.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/students/${regNo}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            alert(`Student ${regNo} deleted successfully.`);
            loadHistoryLogs();
        } else {
            const data = await res.json();
            alert(`Error: ${data.detail || 'Failed to delete.'}`);
        }
    } catch (err) {
        alert("Failed to connect to server to delete student.");
    }
}

function exportPDF() {
    const selectedDate = elements.historyDate.value;
    if (!selectedDate) {
        showToast("Please select a date first.", "toast-warning");
        return;
    }

    const filterVal = document.getElementById('history-filter') ? document.getElementById('history-filter').value : 'all';
    const url = `/api/attendance/export?date=${selectedDate}&view=${state.historyViewMode}&filter=${filterVal}`;

    showToast("Downloading PDF...", "toast-info");
    window.location.href = url;
}

function exportExcel() {
    const selectedDate = elements.historyDate.value;
    if (!selectedDate) {
        showToast("Please select a date first.", "toast-warning");
        return;
    }

    const filterVal = document.getElementById('history-filter') ? document.getElementById('history-filter').value : 'all';
    const url = `/api/attendance/export/excel?date=${selectedDate}&view=${state.historyViewMode}&filter=${filterVal}`;

    showToast("Downloading Excel spreadsheet...", "toast-info");
    window.location.href = url;
}

// 9. HELPER FUNCTIONS
function showFeedback(panel, message, type) {
    panel.innerHTML = message;
    panel.className = `feedback-panel ${type}`;
    panel.style.display = 'block';
}

function displayCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString();
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

    toast.innerHTML = `
        <i data-lucide="${iconName}" class="toast-icon"></i>
        <span class="toast-message">${message}</span>
    `;

    container.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
        toast.classList.add('toast-fadeOut');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    }, 4000);
}
