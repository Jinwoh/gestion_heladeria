document.addEventListener("DOMContentLoaded", () => {
  const dataNode = document.getElementById("dashboard-chart-data");
  if (!dataNode) return;
  const periodSelect = document.getElementById("periodSelect");
  periodSelect?.addEventListener("change", () => periodSelect.form?.submit());
  if (typeof Chart === "undefined") {
    document.querySelectorAll(".dashboard-chart-error").forEach((element) => { element.hidden = false; });
    return;
  }
  const data = JSON.parse(dataNode.textContent);
  const text = "#c4c9d8";
  const muted = "#7a8299";
  const grid = "rgba(255,255,255,.07)";
  const colors = ["#22c55e", "#3b82f6", "#f59e0b", "#a78bfa", "#f87171"];
  const money = (value) => `Gs. ${Math.round(value).toLocaleString("es-PY")}`;
  const common = { responsive:true, maintainAspectRatio:false, plugins:{ legend:{display:false}, tooltip:{backgroundColor:"#111e35",titleColor:text,bodyColor:text,borderColor:"rgba(255,255,255,.12)",borderWidth:1,callbacks:{label:(context)=>money(context.raw)}} } };
  new Chart(document.getElementById("paymentChart"), { type:"bar", data:{labels:data.payments.labels,datasets:[{data:data.payments.data,backgroundColor:colors.slice(0,3),borderRadius:6,maxBarThickness:42}]}, options:{...common,scales:{y:{beginAtZero:true,grid:{color:grid},ticks:{color:muted,callback:(value)=>money(value)}},x:{grid:{display:false},ticks:{color:muted}}}} });
  new Chart(document.getElementById("trendChart"), { type:"line", data:{labels:data.trend.labels,datasets:[{data:data.trend.data,borderColor:"#22c55e",backgroundColor:"rgba(34,197,94,.10)",fill:true,tension:.32,pointRadius:3,pointBackgroundColor:"#4ade80"}]}, options:{...common,scales:{y:{beginAtZero:true,grid:{color:grid},ticks:{color:muted,callback:(value)=>money(value)}},x:{grid:{display:false},ticks:{color:muted}}}} });
  new Chart(document.getElementById("timelineChart"), {
    data:{labels:data.timeline.labels,datasets:[
      {type:"bar",label:"Facturación",data:data.timeline.sales,backgroundColor:"rgba(59,130,246,.68)",borderColor:"#60a5fa",borderWidth:1,borderRadius:6,maxBarThickness:44,yAxisID:"y"},
      {type:"line",label:"Operaciones",data:data.timeline.operations,borderColor:"#4ade80",backgroundColor:"#4ade80",tension:.32,pointRadius:4,pointHoverRadius:6,yAxisID:"yOperations"}
    ]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:"index",intersect:false},plugins:{legend:{display:true,labels:{color:text,usePointStyle:true,boxWidth:8}},tooltip:{backgroundColor:"#111e35",titleColor:text,bodyColor:text,borderColor:"rgba(255,255,255,.12)",borderWidth:1,callbacks:{label:(context)=>context.dataset.yAxisID==="y"?`${context.dataset.label}: ${money(context.raw)}`:`${context.dataset.label}: ${context.raw}`}}},scales:{y:{beginAtZero:true,position:"left",grid:{color:grid},ticks:{color:muted,callback:(value)=>money(value)}},yOperations:{beginAtZero:true,position:"right",grid:{drawOnChartArea:false},ticks:{color:muted,precision:0}},x:{grid:{display:false},ticks:{color:muted}}}}
  });
  const productEmpty = document.getElementById("productEmpty");
  if (data.products.data.some((value) => value > 0)) {
    new Chart(document.getElementById("productChart"), { type:"doughnut", data:{labels:data.products.labels,datasets:[{data:data.products.data,backgroundColor:colors,borderWidth:0}]}, options:{...common,cutout:"64%",plugins:{...common.plugins,tooltip:{...common.plugins.tooltip,callbacks:{label:(context)=>`${context.label}: ${context.raw}%`}}}} });
    const legend = document.getElementById("productLegend");
    data.products.labels.forEach((label,index) => {
      const item=document.createElement("span"); const dot=document.createElement("span");
      item.className="dashboard-legend-item"; dot.className="dashboard-legend-dot";
      dot.style.backgroundColor=colors[index%colors.length];
      item.append(dot,document.createTextNode(`${label} ${data.products.data[index]}%`)); legend.appendChild(item);
    });
  } else { document.getElementById("productChart").parentElement.hidden=true; productEmpty.hidden=false; }
  const goal=data.goal.target>0?Math.min(100,Math.round(data.goal.current/data.goal.target*100)):0;
  const goalColor=goal>=100?"#4ade80":goal>=75?"#3b82f6":goal>=50?"#f59e0b":"#f87171";
  new Chart(document.getElementById("goalChart"), { type:"doughnut", data:{datasets:[{data:[goal,100-goal],backgroundColor:[goalColor,grid],borderWidth:0}]}, options:{...common,circumference:180,rotation:270,cutout:"76%",plugins:{legend:{display:false},tooltip:{enabled:false}}} });
});
