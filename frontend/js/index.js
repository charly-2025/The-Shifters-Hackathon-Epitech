const filterButtons = document.querySelectorAll(".filter");
console.log(filterButtons);

let select_btn = document.querySelector("#btn-all");
select_btn.classList.add("filter-active");

filterButtons.forEach( button =>{
    button.addEventListener("click",()=>{
        filterButtons.forEach(b => b.classList.remove('filter-active'));
        button.classList.add('filter-active');
        select_btn = button;
    })
})

