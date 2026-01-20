import requests

# Tes identifiants
ID = "bf93f85d-2789-4830-95f0-997af370f3af"
SECRET = "***REMOVED***"

def recuperer_donnees():
    print("1. Demande du token en cours...")
    # URL exacte du nouveau portail
    url_token = "https://portail-api.insee.fr/token"
    
    # On force le type de contenu que l'on envoie
    headers_token = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json"
    }
    
    try:
        r_token = requests.post(
            url_token,
            data={'grant_type': 'client_credentials'},
            auth=(ID, SECRET),
            headers=headers_token
        )
        
        if r_token.status_code != 200:
            print(f"❌ Erreur API ({r_token.status_code})")
            print(f"Réponse du serveur : {r_token.text}")
            return
            
        token = r_token.json()['access_token']
        print("✅ Token obtenu avec succès !")

    except Exception as e:
        print(f"❌ Erreur technique : {e}")
        return

    print("2. Récupération des données de Rennes...")
    url_data = "https://api.insee.fr/donnees-locales/v0.1/donnees/geo-COMMUNE@35238/RP2020_MOBT_IND?croisement=MODPR"
    headers_data = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    r_data = requests.get(url_data, headers=headers_data)
    if r_data.status_code == 200:
        print("✅ DONNÉES REÇUES !")
        with open("rennes.json", "w", encoding="utf-8") as f:
            f.write(r_data.text)
        print("--- Fichier 'rennes.json' créé. ---")
    else:
        print(f"❌ Erreur données ({r_data.status_code}): {r_data.text}")

if __name__ == "__main__":
    recuperer_donnees()