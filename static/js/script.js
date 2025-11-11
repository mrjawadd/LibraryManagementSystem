// small helper to auto-hide bootstrap toasts after 3s
document.addEventListener('DOMContentLoaded', function(){
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach(t => {
      setTimeout(() => {
        t.classList.remove('show');
        t.classList.add('hide');
      }, 3200);
    });
  });
  