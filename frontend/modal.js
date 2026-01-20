const openBtn = document.getElementById("openModal");
const closeBtn = document.getElementById("closeModal");
const overlay = document.getElementById("modalOverlay");

openBtn.addEventListener("click", () => {
  overlay.style.display = "flex";
  document.body.style.overflow = "hidden";
});

closeBtn.addEventListener("click", closeModal);
overlay.addEventListener("click", (e) => {
  if (e.target === overlay) closeModal();
});

function closeModal() {
  overlay.style.display = "none";
  document.body.style.overflow = "auto";
}
