document.addEventListener("DOMContentLoaded", function() {
    
    // ==========================================
    // 1. สร้าง HTML (Sidebar + Header)
    // ==========================================
    const sidebarHTML = `
    <div id="mobile-backdrop" class="fixed inset-0 bg-black/50 z-40 hidden transition-opacity duration-300 opacity-0 md:hidden"></div>

    <div class="flex flex-col h-full bg-white border-r border-gray-200 w-64 transition-all duration-300 ease-in-out bg-white shadow-xl md:shadow-none" id="sidebar-content">
        
        <div class="h-16 flex items-center justify-start px-6 border-b border-gray-200 flex-shrink-0 bg-slate-50 transition-all duration-300 overflow-hidden" id="sidebar-header">
            <div class="w-9 h-9 bg-[#0f172a] rounded-full flex items-center justify-center text-white shadow-sm transition-transform duration-300 flex-shrink-0" id="logo-icon">
                <i class="fas fa-camera text-sm"></i>
            </div>
            <span class="text-lg font-bold text-[#0f172a] uppercase whitespace-nowrap logo-text ml-3 opacity-100 transition-opacity duration-300">MultiSnap</span>
            
            <button id="mobile-close-btn" class="absolute right-4 top-5 text-gray-400 hover:text-gray-600 md:hidden">
                <i class="fas fa-times text-xl"></i>
            </button>
        </div>

        <nav class="flex-1 overflow-y-auto py-4 space-y-1 px-3">
            <a href="/dashboard" class="flex items-center px-3 py-2.5 text-gray-600 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg group mb-1 nav-item transition-all whitespace-nowrap overflow-hidden">
                <div class="w-8 flex-shrink-0 text-center"><i class="fas fa-home group-hover:scale-110 transition-transform"></i></div>
                <span class="text-sm font-medium ml-2 sidebar-text transition-opacity duration-300">Dashboard</span>
            </a>
            <a href="/events" class="flex items-center px-3 py-2.5 text-gray-600 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg group mb-1 nav-item transition-all whitespace-nowrap overflow-hidden">
                <div class="w-8 flex-shrink-0 text-center"><i class="fas fa-calendar-alt group-hover:scale-110 transition-transform"></i></div>
                <span class="text-sm font-medium ml-2 sidebar-text transition-opacity duration-300">Events</span>
            </a>
            <a href="/cloud-settings" class="flex items-center px-3 py-2.5 text-gray-600 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg group mb-1 nav-item transition-all whitespace-nowrap overflow-hidden">
                <div class="w-8 flex-shrink-0 text-center"><i class="fas fa-cloud group-hover:scale-110 transition-transform"></i></div>
                <span class="text-sm font-medium ml-2 sidebar-text transition-opacity duration-300">Cloud Setting</span>
            </a>
            <a href="/line-oa" class="flex items-center px-3 py-2.5 text-gray-600 hover:bg-green-50 hover:text-green-600 rounded-lg group mb-1 nav-item transition-all whitespace-nowrap overflow-hidden">
                <div class="w-8 flex-shrink-0 text-center"><i class="fab fa-line text-lg group-hover:scale-110 transition-transform"></i></div>
                <span class="text-sm font-medium ml-2 sidebar-text transition-opacity duration-300">Line OA Connect</span>
            </a>
            <a href="/watermark-setting" class="flex items-center px-3 py-2.5 text-gray-600 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg group mb-1 nav-item transition-all whitespace-nowrap overflow-hidden">
                <div class="w-8 flex-shrink-0 text-center"><i class="fas fa-stamp group-hover:scale-110 transition-transform"></i></div>
                <span class="text-sm font-medium ml-2 sidebar-text transition-opacity duration-300">Watermark Setting</span>
            </a>
        </nav>

        <div class="p-4 border-t border-gray-100 bg-gray-50">
            <a href="/logout" class="flex items-center px-3 py-2 text-red-600 hover:bg-red-50 border border-transparent hover:border-red-100 rounded-lg nav-item transition-all whitespace-nowrap overflow-hidden">
                <div class="w-8 flex-shrink-0 text-center"><i class="fas fa-power-off"></i></div>
                <span class="text-sm font-bold ml-2 sidebar-text transition-opacity duration-300">Logout</span>
            </a>
        </div>
    </div>`;

    // HEADER: ตัดคำว่า Dashboard ออก เหลือแค่ปุ่ม 3 ขีด
    const headerHTML = `
    <header class="bg-white/90 backdrop-blur-md h-16 flex items-center justify-between px-4 md:px-6 border-b border-gray-200 w-full sticky top-0 z-20 shadow-sm transition-all">
        <div class="flex items-center">
            <button id="main-menu-toggle" class="p-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors focus:outline-none active:scale-95 group">
                <i class="fas fa-bars text-xl group-hover:text-emerald-600 transition-colors"></i>
            </button>
        </div>

        <div class="flex items-center gap-4">
            <div class="relative group">
                <div class="flex items-center gap-2 md:gap-3 cursor-pointer hover:bg-gray-50 p-1 pr-2 rounded-full border border-transparent hover:border-gray-200 transition-all">
                    <div class="text-right hidden sm:block pl-2">
                        <p class="text-sm font-bold text-gray-800 leading-tight" id="js-header-username">Loading...</p>
                        <p class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider" id="js-header-role">...</p>
                    </div>
                    <div id="js-header-avatar" class="w-9 h-9 bg-slate-800 text-white rounded-full flex items-center justify-center font-bold text-sm shadow-md ring-2 ring-white">
                        <i class="fas fa-user"></i>
                    </div>
                </div>
                
                <div class="absolute right-0 top-12 w-48 bg-white rounded-xl shadow-xl border border-gray-100 p-1 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-all transform origin-top-right z-50">
                    <a href="/logout" class="flex items-center px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors font-medium">
                        <i class="fas fa-sign-out-alt mr-2"></i> ออกจากระบบ
                    </a>
                </div>
            </div>
        </div>
    </header>`;

    // ==========================================
    // 2. แปะโค้ดลงหน้าเว็บ
    // ==========================================
    const sidebarContainer = document.getElementById('sidebar-container');
    if (sidebarContainer) {
        // Default: Mobile=Hidden, Desktop=Visible(Full)
        sidebarContainer.className = "fixed inset-y-0 left-0 z-50 transform -translate-x-full md:translate-x-0 md:static md:flex-shrink-0 md:flex md:h-full transition-transform duration-300"; 
        sidebarContainer.innerHTML = sidebarHTML;
    }

    const headerContainer = document.getElementById('header-container');
    if (headerContainer) {
        headerContainer.innerHTML = headerHTML;
    }

    // ==========================================
    // 3. ดึงข้อมูล User
    // ==========================================
    fetch('/api/current-user')
        .then(res => res.json())
        .then(data => {
            const userEl = document.getElementById('js-header-username');
            const roleEl = document.getElementById('js-header-role');
            const avatarEl = document.getElementById('js-header-avatar');
            
            if (data.user) {
                let displayName = data.user.includes('@') ? data.user.split('@')[0] : data.user;
                if(userEl) userEl.textContent = displayName;
                if(avatarEl) {
                    avatarEl.textContent = displayName.charAt(0).toUpperCase();
                    avatarEl.classList.remove('bg-slate-800');
                    if (data.role === 'admin') {
                        avatarEl.classList.add('bg-emerald-600');
                        if(roleEl) { roleEl.textContent = 'Super Admin'; roleEl.className = "text-[10px] font-bold text-emerald-600 uppercase tracking-wider"; }
                    } else {
                        avatarEl.classList.add('bg-blue-600');
                        if(roleEl) { roleEl.textContent = 'Member'; roleEl.className = "text-[10px] font-bold text-blue-500 uppercase tracking-wider"; }
                    }
                }
            } else {
                if(userEl) userEl.textContent = "Guest";
            }
        })
        .catch(err => console.error(err));

    // ==========================================
    // 4. เริ่มระบบเมนู (Logic รวม Mobile + Desktop)
    // ==========================================
    initializeMenuSystem();
});

function initializeMenuSystem() {
    const sidebarContainer = document.getElementById('sidebar-container');
    const sidebarContent = document.getElementById('sidebar-content');
    const backdrop = document.getElementById('mobile-backdrop');
    
    // ฟังก์ชันเปิด/ปิด Mobile Drawer
    function toggleMobileMenu(show) {
        if (show) {
            sidebarContainer.classList.remove('-translate-x-full');
            backdrop.classList.remove('hidden');
            setTimeout(() => backdrop.classList.remove('opacity-0'), 10);
        } else {
            sidebarContainer.classList.add('-translate-x-full');
            backdrop.classList.add('opacity-0');
            setTimeout(() => backdrop.classList.add('hidden'), 300);
        }
    }

    // ฟังก์ชันย่อ/ขยาย Desktop Sidebar (Mini Mode)
    function toggleDesktopSidebar() {
        const isExpanded = sidebarContent.classList.contains('w-64');
        
        if (isExpanded) {
            // ย่อ (Collapse)
            sidebarContent.classList.remove('w-64');
            sidebarContent.classList.add('w-20');
            
            // ปรับ Logo ให้ไปอยู่ตรงกลาง
            const header = sidebarContent.querySelector('#sidebar-header');
            header.classList.remove('px-6', 'justify-start');
            header.classList.add('px-0', 'justify-center');

            // ซ่อนข้อความ
            sidebarContent.querySelectorAll('.sidebar-text, .logo-text').forEach(el => {
                el.classList.add('hidden'); // หรือใช้ opacity-0 ถ้าอยากให้เฟด
            });
        } else {
            // ขยาย (Expand)
            sidebarContent.classList.remove('w-20');
            sidebarContent.classList.add('w-64');

            // ปรับ Logo กลับที่เดิม
            const header = sidebarContent.querySelector('#sidebar-header');
            header.classList.add('px-6', 'justify-start');
            header.classList.remove('px-0', 'justify-center');

            // แสดงข้อความ
            sidebarContent.querySelectorAll('.sidebar-text, .logo-text').forEach(el => {
                el.classList.remove('hidden');
            });
        }
    }

    // รวม Event Listener ไว้ที่ปุ่มเดียว
    document.addEventListener('click', function(e) {
        const toggleBtn = e.target.closest('#main-menu-toggle');
        const mobileCloseBtn = e.target.closest('#mobile-close-btn');
        const clickedBackdrop = e.target.closest('#mobile-backdrop');
        const clickedLink = e.target.closest('.nav-item');

        const isMobile = window.innerWidth < 768;

        // 1. กดปุ่ม 3 ขีด (Hamburger)
        if (toggleBtn) {
            e.preventDefault();
            if (isMobile) {
                toggleMobileMenu(true); // มือถือ: เปิด Drawer
            } else {
                toggleDesktopSidebar(); // คอม: ย่อ/ขยาย เมนู
            }
        }

        // 2. ปิดเมนู (กดกากบาท / กดพื้นหลัง / กดลิ้งค์บนมือถือ)
        else if (mobileCloseBtn || clickedBackdrop || (clickedLink && isMobile)) {
            if (isMobile) toggleMobileMenu(false);
        }
    });

    // Highlight Menu
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('#sidebar-content a');
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && (href === currentPath || (href !== '/dashboard' && currentPath.startsWith(href)))) {
            link.classList.remove('text-gray-600', 'hover:bg-emerald-50');
            link.classList.add('bg-emerald-50', 'text-emerald-600', 'font-bold', 'shadow-sm');
        }
    });
}