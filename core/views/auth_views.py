from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

# ==============================================================================
# VIEW OTENTIKASI (Authentication Filters)
# ==============================================================================

def landing_view(request):
    """Halaman Landing awal aplikasi sebelum Login."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'pages/landing.html')

# --------------------------------------------------------------------------
# LOGIKA LOGIN & LOGOUT
# --------------------------------------------------------------------------

def login_view(request):
    """Mengelola proses masuk (Login) ke dalam sistem."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # Proses Validasi User
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Username atau password salah.')
    
    return render(request, 'pages/login.html')

def logout_view(request):
    """Keluar dari sistem dan menghapus sesi (Session)."""
    logout(request)
    return redirect('login')
