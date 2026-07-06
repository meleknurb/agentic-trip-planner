// static/js/settings.js

// Centralized client-side tab management and flash dismissal workflow
document.addEventListener("DOMContentLoaded", function() {
    
    // Activate the tab based on the data attribute from the container
    const container = document.querySelector('.settings-container');
    if (container) {
        const backendTab = container.getAttribute('data-backend-tab');
        if (backendTab) {
            switchTab(backendTab);
        }
    }

    // Automatically dismiss flash messages after a delay
    const alerts = document.querySelectorAll('.flash-messages .alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.classList.add('alert-hiding');
            
            setTimeout(function() {
                alert.remove();
            }, 200);
        }, 2000);
    });
});

// Function to switch between tabs
function switchTab(tabName) {
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });

    const targetSection = document.getElementById(`${tabName}-tab`);
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    let targetBtn = document.getElementById(`btn-${tabName}`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }
}

// Event listeners for tab buttons
document.querySelectorAll('.custom-select').forEach(select => {
    select.addEventListener('click', () => {
        select.classList.toggle('active');
    });
});

// Event listeners for select options
document.querySelectorAll('.select-option').forEach(option => {
    option.addEventListener('click', (e) => {
        const parent = option.closest('.custom-select');
        parent.querySelector('.select-trigger').textContent = option.textContent;
        parent.parentElement.querySelector('input[type="hidden"]').value = option.getAttribute('data-value');
    });
});

// Close the custom select dropdown when clicking outside of it
document.addEventListener('click', (event) => {
    if (!event.target.closest('.custom-select')) {
        document.querySelectorAll('.custom-select').forEach(select => {
            select.classList.remove('active');
        });
    }
});

// Confirm account deletion
function confirmDelete() {
    document.getElementById('deleteModal').style.display = 'block';
}

// Close the modal when clicking outside of it
function closeModal() {
    document.getElementById('deleteModal').style.display = 'none';
}

document.getElementById('deleteModal').addEventListener('click', function(event) {
    if (event.target === this) {
        closeModal();
    }
});