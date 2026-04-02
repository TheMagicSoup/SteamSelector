async function loadRecommendations(){
    try{
        const res=await fetch("/api/recommend");
        const data=await res.json();
        console.log(data)
        const container=document.getElementById("recommendations");
        const loading=document.getElementById("loading");
        loading.style.display="none";
        data.forEach(game=>{
            const div=document.createElement("div");
            div.innerHTML=`
                <h3>${game.name}</h3>
                <img src="https://cdn.cloudflare.steamstatic.com/steam/apps/${game.appid}/header.jpg" width="300">
                <br>
                <a href="https://store.steampowered.com/app/${game.appid}" target="_blank">
                    View on Steam
                </a>
                <hr>
            `;
            container.appendChild(div);
        });

    } catch (err){
        console.error("Error loading recommendations:",err);
    }
}

window.onload=loadRecommendations;