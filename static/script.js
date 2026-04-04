async function loadRecommendations(){
    try{
        const res=await fetch("/api/recommend");
        const data=await res.json();
        console.log(data)
        const container=document.getElementById("recommendations");
        const loading=document.getElementById("loading");
        loading.style.display="none";
        data.forEach(game=>{
            const row=document.createElement("div");
            row.className="resultsrecommendedrow resultsbody";

            const nameDiv=document.createElement("div");
            nameDiv.textContent=game.name;

            const img = document.createElement("img");
            img.className="results";
            img.src=`https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/${game.appid}/capsule_231x87.jpg`;
            img.alt=`${game.name} Header Image`;

            img.onerror=function(){
                this.onerror=null;
                this.src="/static/assets/assetnotfound.png";
            };
            
            const link=document.createElement("a");
            link.href=`https://store.steampowered.com/app/${game.appid}`;
            link.target="_blank";
            link.appendChild(img);

            const descriptionDiv=document.createElement("div");
            descriptionDiv.className="resultsbody";
            descriptionDiv.textContent=game.description;

            const titleImgDiv=document.createElement("div");
            titleImgDiv.className="resultsgamesrow";
            titleImgDiv.appendChild(nameDiv);
            titleImgDiv.appendChild(link);

            row.append(titleImgDiv);
            row.appendChild(descriptionDiv);
            
            container.appendChild(row);
        });

    } catch (err){
        console.error("Error loading recommendations:",err);
    }
}

window.onload=loadRecommendations;