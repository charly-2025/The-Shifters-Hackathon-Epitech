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



function create_city_card(){
    let city_card = document.createElement("div");
    city_card.classList.add("city");
    return city_card;
}

function create_city_header(name,dep,hab,sc_global){
    let city_header = document.createElement("div");
    city_header.classList.add("name-stat-grade");

    let city_name_stat = document.createElement("div");
    city_name_stat.classList.add("name-stat");

    let name_city = document.createElement("p");
    name_city.classList.add("open-btn");
    name_city.setAttribute("id","openModal");
    name_city.textContent = name;

    let stat_city = document.createElement("div");
    stat_city.classList.add("stat");

    let loc_city = document.createElement("div");
    loc_city.classList.add("loc");
    loc_city.textContent = dep;

    let hab_city = document.createElement("div");
    hab_city.classList.add("hab");
    hab_city.textContent = hab+" hab.";

    let score_global = document.createElement("div");
    score_global.classList.add("global");
    score_global.textContent=sc_global+"/100";

     if( sc_global < 76 && sc_global > 49){
        score_global.style.color = "#dd891a";
    } else if ( sc_global < 50) {
        score_global.style.color = "#dd4d1a";
    }


    stat_city.appendChild(loc_city);
    stat_city.appendChild(hab_city);

    city_name_stat.appendChild(name_city);
    city_name_stat.appendChild(stat_city);

    city_header.appendChild(city_name_stat);
    city_header.appendChild(score_global);

    return city_header
}


function createGrade(label, score) {
    const grade = document.createElement("div");
    grade.classList.add("grade");

    const name = document.createElement("div");
    name.classList.add("name");

    const labelP = document.createElement("p");
    labelP.textContent = label;

    const scoreP = document.createElement("p");
    scoreP.textContent = score + "/100";

    name.appendChild(labelP);
    name.appendChild(scoreP);

    const jauge = document.createElement("div");
    jauge.classList.add("jauge");

    const jaugeRemplie = document.createElement("div");
    jaugeRemplie.classList.add("jauge-remplie");
    jaugeRemplie.style.width = score + "%";

    if( score < 76 && score > 49){
        jaugeRemplie.style.backgroundColor = "#dd891a";
    } else if ( score < 50) {
        jaugeRemplie.style.backgroundColor = "#dd4d1a";
    }

    jauge.appendChild(jaugeRemplie);

    grade.appendChild(name);
    grade.appendChild(jauge);

    return grade;
}


function createCityGrades(sc_mob, sc_elec, sc_bio, sc_dech, sc_sob) {
    const fiveGrades = document.createElement("div");
    fiveGrades.classList.add("five-grades");

    fiveGrades.appendChild(createGrade("Mobilité", sc_mob));
    fiveGrades.appendChild(createGrade("Energie", sc_elec));
    fiveGrades.appendChild(createGrade("Biodiversité", sc_bio));
    fiveGrades.appendChild(createGrade("Déchets", sc_dech));
    fiveGrades.appendChild(createGrade("Sobriété", sc_sob));

    return fiveGrades;

}


function add_city(name,dep,hab,sc_global,sc_mob,sc_elec,sc_bio,sc_dech,sc_sob){
    

    city_card = create_city_card();
    
    city_card.appendChild(create_city_header(name,dep,hab,sc_global));
    city_card.appendChild(createCityGrades(sc_mob,sc_elec,sc_bio,sc_dech,sc_sob));
    
    compare_button = document.createElement("button");
    compare_button.classList.add("compare");
    compare_button.textContent = "Sélectionner pour comparer";

    city_card.appendChild(compare_button)
    
    document.querySelector(".container-city").appendChild(city_card);

}


add_city("luxembourg","35000 . aquitaine",3549400,30,88,46,20,75,83);