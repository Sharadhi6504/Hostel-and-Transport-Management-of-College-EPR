// Simple theme toggle storing preference in localStorage
(function(){
  const root = document.documentElement;
  const toggle = () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  };
  const init = () => {
    const stored = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', stored);
    const btn = document.getElementById('themeToggle');
    if(btn) btn.addEventListener('click', toggle);
  };
  document.addEventListener('DOMContentLoaded', init);
})();
