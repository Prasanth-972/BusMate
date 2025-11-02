from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
import os
import requests
import logging
from decimal import Decimal
from .models import BusRoute, BusPassApplication, UserProfile, SupportMessage, BoardingLocation
from .forms import BusRouteForm, BusPassApplicationForm, UserRegistrationForm, UserProfileEditForm

logger = logging.getLogger(__name__)

# --- Helper Functions for User Type Check ---
def is_admin(user):
    try:
        return user.is_authenticated and user.userprofile.is_admin
    except UserProfile.DoesNotExist:
        return False

def is_normal_user(user):
    try:
        return user.is_authenticated and not user.userprofile.is_admin
    except UserProfile.DoesNotExist:
        return user.is_authenticated # Treat users without profile as normal users

# --- Initial Page & Dashboard Views ---

def initial_page(request):
    """The landing page with About Us and Login."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Note: Login form is handled by Django's auth system (template required)
    form = AuthenticationForm()
    form.fields['username'].widget.attrs.update({'class': 'inputField', 'placeholder': 'Username'})
    form.fields['password'].widget.attrs.update({'class': 'inputField', 'placeholder': 'Password'})
    return render(request, 'BusPass/initial_page.html', {'form': form})

def register(request):
    """User registration view with photo upload."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log in the user after registration
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def dashboard(request):
    """Directs to the appropriate dashboard based on user type."""
    if is_admin(request.user):
        return redirect('admin_dashboard') # Create this URL/View
    else:
        return redirect('user_dashboard') # Create this URL/View

# --- Normal User Views ---

@login_required
@user_passes_test(is_normal_user, login_url='/accounts/login/')
def user_dashboard(request):
    return render(request, 'BusPass/user_dashboard.html')

@login_required
def view_routes(request):
    routes = BusRoute.objects.all()
    return render(request, 'BusPass/view_routes.html', {'routes': routes})

@login_required
def apply_for_pass(request, route_id):
    route = get_object_or_404(BusRoute, id=route_id)
    
    # Check if a pending/active pass already exists
    existing_pass = BusPassApplication.objects.filter(
        user=request.user, 
        route=route, 
        status__in=['PENDING', 'PAID', 'ALLOCATED']
    ).exists()
    
    if existing_pass:
        # Prevent re-application
        return render(request, 'BusPass/application_error.html', 
                      {'message': 'You already have an active or pending application for this route.'})
    
    if request.method == 'POST':
        form = BusPassApplicationForm(request.POST, route=route)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.route = route
            application.status = 'PENDING' # Application starts as PENDING
            # Compute discounted fee based on boarding location position
            bl_name = application.boarding_location
            discount = Decimal('0')
            try:
                bl = BoardingLocation.objects.get(route=route, name=bl_name)
                # reduction is 150 per option number (1-based): 1->150, 2->300, ...
                discount = Decimal('150') * Decimal(bl.position)
            except BoardingLocation.DoesNotExist:
                pass
            # Ensure non-negative
            try:
                base_fee = Decimal(route.fee)
            except Exception:
                base_fee = Decimal('0')
            application.paid_fee = max(base_fee - discount, Decimal('0'))
            application.save()
            
            # --- Payment Simulation ---
            # In a real system, this redirects to a payment gateway.
            # Here, we'll simulate success and move to the 'PAID' status.
            application.status = 'PAID' 
            application.save()

            # Update user's preferred boarding location
            try:
                profile = request.user.userprofile
                profile.preferred_boarding_location = application.boarding_location
                profile.save()
            except UserProfile.DoesNotExist:
                pass
            
            return redirect('payment_success')
    else:
        form = BusPassApplicationForm(route=route)
    
    return render(request, 'BusPass/apply_for_pass.html', {'form': form, 'route': route})

def payment_success(request):
    """A page confirming simulated payment success."""
    return render(request, 'BusPass/payment_success.html')

@login_required
def my_pass(request):
    """View the user's latest bus pass and its status."""
    latest_pass = BusPassApplication.objects.filter(user=request.user).order_by('-application_date').first()
    return render(request, 'BusPass/my_pass.html', {'bus_pass': latest_pass})


@login_required
def edit_profile(request):
    """Allow users to edit their profile information and photo."""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        # Create a profile if it doesn't exist
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('user_dashboard')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = UserProfileEditForm(instance=profile)
    
    return render(request, 'BusPass/edit_profile.html', {
        'form': form,
    })


@login_required
def change_password(request):
    """Allow users to change their password."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important to keep the user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('edit_profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'BusPass/change_password.html', {
        'form': form,
    })

@login_required
def cancel_pass(request, pass_id):
    """Allow a user to cancel their own bus pass when not yet allocated."""
    bus_pass = get_object_or_404(BusPassApplication, id=pass_id, user=request.user)

    if request.method != 'POST':
        raise Http404()

    if bus_pass.status in ['PENDING', 'PAID']:
        bus_pass.status = 'CANCELLED'
        bus_pass.seat_number = None
        bus_pass.save()
        messages.success(request, 'Your bus pass application has been cancelled.')
    else:
        messages.error(request, 'This pass cannot be cancelled at its current status.')

    return redirect('my_pass')

@login_required
def submit_support_message(request):
    """AJAX endpoint to save a support message from the current user."""
    if request.method != 'POST':
        raise Http404()
    msg = (request.POST.get('message') or '').strip()
    if not msg:
        return JsonResponse({'ok': False, 'error': 'Empty message'}, status=400)
    SupportMessage.objects.create(user=request.user, message=msg)
    return JsonResponse({'ok': True})

@require_POST
@login_required
def ai_support_chat(request):
    """Simple AI chat endpoint.
    - If HUGGINGFACE_API_KEY is set, calls a small instruct model on HF Inference API.
    - Otherwise, falls back to keyword-based FAQ responses.
    Returns JSON: { ok: True, reply: str }
    """
    user_msg = (request.POST.get('message') or '').strip()
    if not user_msg:
        return JsonResponse({'ok': False, 'error': 'Empty message'}, status=400)

    # 1) Try local Ollama first, if running (chat API)
    ollama_model = os.environ.get('OLLAMA_MODEL', 'llama3:latest')
    try:
        system_msg = (
            "You are a friendly support assistant for a college bus pass system called Busmate. "
            "Answer concisely. If asked about status or steps, list clear steps."
        )
        body = {
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 180},
        }
        resp = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json=body,
            timeout=20,
        )
        if resp.ok:
            data = resp.json()
            # Expect { message: { role, content }, ... }
            msg = (data.get('message') or {})
            reply = (msg.get('content') or '').strip()
            if reply:
                return JsonResponse({"ok": True, "reply": reply})
        else:
            logger.warning("Ollama (chat) responded non-OK: %s %s", resp.status_code, resp.text[:300])
    except Exception as e:
        logger.exception("Ollama (chat) request failed: %s", e)

    # 2) Try Hugging Face Inference API if key is available
    hf_key = os.environ.get('HUGGINGFACE_API_KEY')
    if hf_key:
        try:
            # Keep prompt short and safe for a lightweight response
            prompt = (
                "You are a friendly support assistant for a college bus pass system called Busmate. "
                "Answer concisely. If asked about status or steps, list clear steps.\n\n"
                f"User: {user_msg}\nAssistant:"
            )
            headers = {"Authorization": f"Bearer {hf_key}", "Content-Type": "application/json"}
            # Choose a small instruct model for faster responses
            model = "microsoft/Phi-3-mini-4k-instruct"
            resp = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers,
                json={"inputs": prompt, "parameters": {"max_new_tokens": 180, "temperature": 0.2}},
                timeout=20,
            )
            if resp.ok:
                data = resp.json()
                # API may return a list of dicts with 'generated_text'
                if isinstance(data, list) and data and 'generated_text' in data[0]:
                    full = data[0]['generated_text']
                    reply = full.split("Assistant:")[-1].strip() or full.strip()
                else:
                    # Some models return a dict with generated_text or text
                    reply = (data.get('generated_text') or data.get('text') or 'Sorry, I could not generate a reply.').strip()
                return JsonResponse({'ok': True, 'reply': reply})
            else:
                logger.warning("HF responded non-OK: %s %s", resp.status_code, resp.text[:300])
        except Exception as e:
            logger.exception("HF request failed: %s", e)

    # Fallback: simple keyword-based FAQ
    lower = user_msg.lower()
    if any(k in lower for k in ["route", "routes", "bus"]):
        reply = (
            "To view routes, go to 'View Routes' from your dashboard. "
            "Click a route to apply, fill the form, and submit."
        )
    elif any(k in lower for k in ["apply", "application", "pass"]):
        reply = (
            "Apply by choosing a route, completing the form, and submitting. "
            "Your status will be PENDING, then PAID (simulated), and an admin may ALLOCATE a seat."
        )
    elif any(k in lower for k in ["status", "allocated", "seat"]):
        reply = (
            "Check 'My Bus Pass' to see the latest status. If ALLOCATED, you'll see your seat number and can download the pass."
        )
    elif any(k in lower for k in ["cancel", "refund"]):
        reply = (
            "You can cancel a PENDING or PAID application from 'My Bus Pass' using the Cancel button."
        )
    elif any(k in lower for k in ["login", "register", "account"]):
        reply = (
            "Use Login from the navbar or register at /buspass/register/. If login fails, make sure cookies are enabled and retry."
        )
    else:
        reply = (
            "I can help with routes, applying for a pass, status, allocation, and cancellations. "
            "Please share more details about your question."
        )
    return JsonResponse({'ok': True, 'reply': reply})

# In a real scenario, you'd use a PDF library (like ReportLab or WeasyPrint)
@login_required
def download_buspass(request, pass_id):
    bus_pass = get_object_or_404(BusPassApplication, id=pass_id, user=request.user)

    if bus_pass.status != 'ALLOCATED':
        raise Http404("Bus Pass not yet allocated/processed.")

    # Simple text response as a placeholder for a PDF download
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="buspass_{bus_pass.id}.txt"'
    
    content = f"""
    --- BUSMATE COLLEGE BUS PASS ---
    Student: {bus_pass.user.get_full_name() or bus_pass.user.username}
    Route: {bus_pass.route.name}
    Boarding Point: {bus_pass.boarding_location}
    Seat Number: {bus_pass.seat_number}
    Status: VALID
    Date Issued: {bus_pass.application_date.strftime('%Y-%m-%d')}
    """
    response.write(content)
    return response

# --- Admin Views ---

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_dashboard(request):
    return render(request, 'BusPass/admin_dashboard.html')

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_add_route(request):
    if request.method == 'POST':
        form = BusRouteForm(request.POST)
        if form.is_valid():
            route = form.save()
            # Parse and save boarding locations if provided
            raw = (form.cleaned_data.get('boarding_locations') or '').strip()
            if raw:
                # Split by newlines and commas while preserving order
                parts = []
                for line in raw.splitlines():
                    for p in line.split(','):
                        name = p.strip()
                        if name:
                            parts.append(name)
                # Stable de-duplication preserving first occurrence order
                seen = set()
                ordered = []
                for name in parts:
                    if name not in seen:
                        seen.add(name)
                        ordered.append(name)
                # Save with 1-based position
                for idx, name in enumerate(ordered, start=1):
                    obj, _ = BoardingLocation.objects.get_or_create(route=route, name=name)
                    if obj.position != idx:
                        obj.position = idx
                        obj.save(update_fields=['position'])
            return redirect('admin_view_routes')
    else:
        form = BusRouteForm()
    return render(request, 'BusPass/admin_add_route.html', {'form': form})

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_edit_route(request, route_id):
    route = get_object_or_404(BusRoute, id=route_id)
    if request.method == 'POST':
        form = BusRouteForm(request.POST, instance=route)
        if form.is_valid():
            form.save()
            return redirect('admin_view_routes')
    else:
        form = BusRouteForm(instance=route)
    return render(request, 'BusPass/admin_edit_route.html', {'form': form, 'route': route})

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_view_routes(request):
    routes = BusRoute.objects.all()
    return render(request, 'BusPass/admin_view_routes.html', {'routes': routes})

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_view_applications(request):
    applications = BusPassApplication.objects.all().order_by('-application_date')
    return render(request, 'BusPass/admin_view_applications.html', {'applications': applications})

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_process_pass(request, pass_id):
    application = get_object_or_404(BusPassApplication, id=pass_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'allocate' and application.status == 'PAID':
            # Simple seat allocation logic: find the next available seat number for this route
            current_count = BusPassApplication.objects.filter(
                route=application.route, status='ALLOCATED'
            ).count()
            
            if current_count < application.route.max_seats:
                application.seat_number = f"S-{current_count + 1:03d}"
                application.status = 'ALLOCATED'
                application.save()
            else:
                # Handle bus full scenario
                # You might set status to 'PENDING_WAITLIST' or similar
                pass 
                
        elif action == 'reject':
            application.status = 'REJECTED'
            application.save()
            
        return redirect('admin_view_applications')

    return render(request, 'BusPass/admin_process_pass.html', {'application': application})