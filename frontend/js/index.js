const filterButtons = document.querySelectorAll(".filter");
console.log(filterButtons);
let currentFilter = "all";

let select_btn = document.querySelector("#btn-all");
select_btn.classList.add("filter-active");

filterButtons.forEach(button => {
    button.addEventListener("click", () => {
        filterButtons.forEach(b => b.classList.remove("filter-active"));
        button.classList.add("filter-active");

        currentFilter = button.id.replace("btn-", "");
        updateCitiesByFilter(currentFilter);
    });
});


function applyCurrentFilter() {
    updateCitiesByFilter(currentFilter);
}
function cityAlreadyExists(name) {
    return !!document.querySelector(`.city[data-city="${name}"]`);
}


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
        jaugeRemplie.style.backgroundColor = "#ce0b07ff";
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
    fiveGrades.appendChild(createGrade("Biodiversité", sc_bio));
    fiveGrades.appendChild(createGrade("Sobriété", sc_sob));

    return fiveGrades;

}


function add_city(name, dep, hab, sc_global, sc_mob, sc_elec, sc_bio, sc_dech, sc_sob) {
    if (cityAlreadyExists(name)) return;

    const city_card = create_city_card();
    city_card.dataset.city = name;

    city_card.appendChild(create_city_header(name, dep, hab, sc_global));

    const cityScores = { mob: sc_mob, elec: sc_elec, bio: sc_bio, dech: sc_dech, sob: sc_sob };

    let grades;
    if (currentFilter === "all") {
        grades = createCityGrades(sc_mob, sc_elec, sc_bio, sc_dech, sc_sob);
    } else {
        const { label, key } = filterMap[currentFilter];
        grades = createCityGradesSingle(label, cityScores[key]);
    }

    city_card.appendChild(grades);

    const compare_button = document.createElement("button");
    compare_button.classList.add("compare");
    compare_button.textContent = "Sélectionner pour comparer";
    city_card.appendChild(compare_button);

    document.querySelector(".container-city").appendChild(city_card);
}





const input = document.querySelector(".search-input");
const suggestionsBox = document.querySelector(".suggestions");
const addBtn = document.querySelector(".add-city-btn");

let selectedCity = null;




const citiesData = {
    Rennes: {
        dep: "35000 · Bretagne",
        hab: 220488,
        global: 82,
        mob: 88,
        elec: 79,
        bio: 76,
        dech: 81,
        sob: 85
    },
    Paris: {
        dep: "75000 · Île-de-France",
        hab: 2148327,
        global: 78,
        mob: 85,
        elec: 70,
        bio: 65,
        dech: 80,
        sob: 75
    },
    Lyon: {
        dep: "69000 · Auvergne-Rhône-Alpes",
        hab: 515695,
        global: 80,
        mob: 83,
        elec: 75,
        bio: 72,
        dech: 78,
        sob: 80
    }
};

const filterMap = {
    all: null,
    mobil: { label: "Mobilité", key: "mob" },
    ene: { label: "Energie", key: "elec" },
    bio: { label: "Biodiversité", key: "bio" },
    dec: { label: "Déchets", key: "dech" },
    sob: { label: "Sobriété", key: "sob" }
};

function createCityGradesSingle(label, score) {
    const fiveGrades = document.createElement("div");
    fiveGrades.classList.add("five-grades");

    fiveGrades.appendChild(createGrade(label, score));

    const dataDiv = document.createElement("div");
    dataDiv.classList.add("category-data");
    dataDiv.textContent = "Données détaillées à venir";
    dataDiv.style.color = "white";

    fiveGrades.appendChild(dataDiv);

    return fiveGrades;
}



input.addEventListener("input", () => {
    const value = input.value.trim().toLowerCase();
    suggestionsBox.innerHTML = "";
    addBtn.style.display = "none";
    selectedCity = null;

    if (value.length < 2) return;

    citySuggestions
        .filter(city => city.toLowerCase().includes(value))
        .slice(0, 10)
        .forEach(city => {
            const item = document.createElement("div");
            item.classList.add("suggestion-item");
            item.innerHTML = `<i class="fas fa-search"></i> ${city}`;

            item.addEventListener("click", () => {
                input.value = city;
                selectedCity = city;
                suggestionsBox.innerHTML = "";
                addBtn.style.display = "block";
            });

            suggestionsBox.appendChild(item);
        });
});




document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) {
        suggestionsBox.innerHTML = "";
    }
});

addBtn.addEventListener("click", async () => {
    if (!selectedCity) return;

    try {
        const data = await fetchEcoCity(selectedCity);
        const city = mapBackendCityToFrontend(data);

        add_city(
            city.name,
            city.dep,
            city.hab,
            city.global,
            city.mob,
            city.elec,
            city.bio,
            city.dech,
            city.sob
        );

    } catch (err) {
        console.error(err);
        alert("Impossible de récupérer les données de la ville");
    }

    input.value = "";
    selectedCity = null;
    addBtn.style.display = "none";
});


const resetBtn = document.querySelector(".reset-btn");
const containerCity = document.querySelector(".container-city");

resetBtn.addEventListener("click", () => {
    containerCity.innerHTML = "";
});

function updateCitiesByFilter(filterKey) {
    document.querySelectorAll(".city").forEach(cityCard => {
        const cityName = cityCard.dataset.city;
        const city = citiesData[cityName];

        const oldGrades = cityCard.querySelector(".five-grades");

        let newGrades;
        if (filterKey === "all") {
            newGrades = createCityGrades(city.mob, city.elec, city.bio, city.dech, city.sob);
        } else {
            const { label, key } = filterMap[filterKey];
            newGrades = createCityGradesSingle(label, city[key]);
        }

        oldGrades.replaceWith(newGrades);
    });
}


let cities = [];

// Sélecteurs
const populationRange = document.getElementById("populationRange");
const populationInput = document.getElementById("populationInput");

const scoreRange = document.getElementById("scoreRange");
const scoreInput = document.getElementById("scoreInput");

// Fonction pour scanner les villes présentes dans le DOM
function collectCitiesFromDOM() {
    const cityElements = document.querySelectorAll(".city");

    cities = Array.from(cityElements).map(city => {
        const habText = city.querySelector(".hab")?.textContent || "0";
        const habitants = Number(habText.replace(/\D/g, ""));

        const scoreText = city.querySelector(".global")?.textContent || "0";
        const score = Number(scoreText.split("/")[0]);

        return {
            element: city,
            habitants,
            score
        };
    });

    updatePopulationLimits();
    filterCities();
}

// Met à jour la valeur max du slider
function updatePopulationLimits() {
    if (!cities.length) return;

    const maxPop = Math.max(...cities.map(c => c.habitants));

    populationRange.min = 0;
    populationRange.max = maxPop;
    populationInput.min = 0;
    populationInput.max = maxPop;

    // Si jamais vide → reset
    if (!populationRange.value || populationRange.value > maxPop) {
        populationRange.value = maxPop;
        populationInput.value = maxPop;
    }
}

// Fonction de filtre
function filterCities() {
    const popMax = Number(populationRange.value || Infinity);
    const scoreMin = Number(scoreRange.value || 0);

    cities.forEach(city => {
        const visible =
            city.habitants <= popMax &&
            city.score >= scoreMin;

        city.element.style.display = visible ? "" : "none";
    });
}

// Sync slider → input
populationRange.addEventListener("input", () => {
    populationInput.value = populationRange.value;
    filterCities();
});

scoreRange.addEventListener("input", () => {
    scoreInput.value = scoreRange.value;
    filterCities();
});

// Sync input → slider
populationInput.addEventListener("input", () => {
    let v = Number(populationInput.value);
    if (v < 0) v = 0;
    if (v > populationRange.max) v = populationRange.max;

    populationRange.value = v;
    filterCities();
});

scoreInput.addEventListener("input", () => {
    let v = Number(scoreInput.value);
    if (v < 0) v = 0;
    if (v > 100) v = 100;

    scoreRange.value = v;
    filterCities();
});

const cityContainer = document.querySelector(".container-city");

if (cityContainer) {
    const observer = new MutationObserver(() => {
        collectCitiesFromDOM();
    });

    observer.observe(cityContainer, {
        childList: true,
        subtree: false
    });
}

// Sécurité au chargement initial
document.addEventListener("DOMContentLoaded", () => {
    collectCitiesFromDOM();
});



async function fetchEcoCity(city) {
    const response = await fetch(
        `http://127.0.0.1:8000/eco?city=${encodeURIComponent(city)}`
    );

    if (!response.ok) {
        throw new Error("Erreur serveur");
    }

    return await response.json();
}

function scoreElectricity(kwhPerHab) {
    if (!kwhPerHab) return null;

    if (kwhPerHab < 2500) return 90;
    if (kwhPerHab < 3500) return 75;
    if (kwhPerHab < 4500) return 60;
    return 40;
}


function scoreBiodiversity(greenSurface) {
    if (!greenSurface) return null;

    if (greenSurface > 40) return 90;
    if (greenSurface > 30) return 75;
    if (greenSurface > 20) return 60;
    return 40;
}

function scoreAirQuality(no2) {
    if (!no2) return null;

    if (no2 < 10) return 90;
    if (no2 < 20) return 75;
    if (no2 < 30) return 60;
    return 40;
}

function averageScore(scores) {
    const validScores = scores.filter(s => typeof s === "number");

    if (validScores.length === 0) return null;

    const sum = validScores.reduce((a, b) => a + b, 0);
    return Math.round(sum / validScores.length);
}

function mapBackendCityToFrontend(data) {
    const elecScore = scoreElectricity(data.kwh_per_inhabitant);
    const bioScore = scoreBiodiversity(data.green_surface); // si dispo plus tard
    const sobScore = scoreAirQuality(data.air_quality?.pollutants?.no2?.value);

    const globalScore = averageScore([
        elecScore,
        bioScore,
        sobScore
    ]);

    return {
        name: data.commune.name,
        dep: `${data.commune.departement} · ${data.commune.region}`,
        hab: data.population?.value ?? 0,

        global: globalScore ?? 0,
        elec: elecScore ?? 0,
        bio: bioScore ?? 0,
        sob: sobScore ?? 0,

        mob: null,
        dech: null
    };
}

const citySuggestions = [
  "Paris",
  "Marseille",
  "Lyon",
  "Toulouse",
  "Nice",
  "Nantes",
  "Montpellier",
  "Strasbourg",
  "Bordeaux",
  "Lille",

  "Rennes",
  "Reims",
  "Le Havre",
  "Saint-Étienne",
  "Toulon",
  "Grenoble",
  "Dijon",
  "Angers",
  "Nîmes",
  "Villeurbanne",

  "Clermont-Ferrand",
  "Le Mans",
  "Aix-en-Provence",
  "Brest",
  "Tours",
  "Amiens",
  "Limoges",
  "Annecy",
  "Perpignan",
  "Boulogne-Billancourt",

  "Metz",
  "Besançon",
  "Orléans",
  "Rouen",
  "Mulhouse",
  "Caen",
  "Nancy",
  "Saint-Denis",
  "Argenteuil",
  "Montreuil",

  "Roubaix",
  "Tourcoing",
  "Avignon",
  "Poitiers",
  "La Rochelle",
  "Chambéry",
  "Bayonne",
  "Angoulême",
  "Brive-la-Gaillarde",
  "Colmar",

  "Évry",
  "Cergy",
  "Pau",
  "Tarbes",
  "Albi",
  "Castres",
  "Montauban",
  "Cahors",
  "Rodez",
  "Millau",

  "Narbonne",
  "Carcassonne",
  "Sète",
  "Agde",
  "Béziers",
  "Arles",
  "Salon-de-Provence",
  "Martigues",
  "Hyères",
  "Draguignan"
];