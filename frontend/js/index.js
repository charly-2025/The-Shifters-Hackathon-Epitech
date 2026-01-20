const filterButtons = document.querySelectorAll(".filter");


filterButtons.forEach( button =>{
    button.addEventListener("click",()=>{
        filterButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    })
})

