(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["pages-index-index"],{"25f3":function(t,e,a){"use strict";var i=a("5fe2"),n=a.n(i);n.a},"5fe2":function(t,e,a){var i=a("8692");i.__esModule&&(i=i.default),"string"===typeof i&&(i=[[t.i,i,""]]),i.locals&&(t.exports=i.locals);var n=a("4f06").default;n("4d73ae59",i,!0,{sourceMap:!1,shadowMode:!1})},8692:function(t,e,a){var i=a("24fb");e=i(!1),e.push([t.i,".home-page .p-main[data-v-7e7ab0b8]{width:100%}.login_title[data-v-7e7ab0b8]{text-align:center;color:#8a2be2;font-weight:700;font-size:30px;margin:0 auto;padding:20px 0;line-height:32px;letter-spacing:5px;background-image:-webkit-linear-gradient(top,#7517cc,rgba(163,9,252,.9333333333333333),#d876e0);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.logim_image[data-v-7e7ab0b8]{width:80%}.logim_imageBox[data-v-7e7ab0b8]{text-align:center}.login_btn[data-v-7e7ab0b8]{background-color:#7517cc;border-radius:20px;width:50%;color:#fff;font-size:20px;font-weight:700;line-height:40px;margin:0 auto 0}",""]),t.exports=e},ac01:function(t,e,a){"use strict";a.d(e,"b",(function(){return i})),a.d(e,"c",(function(){return n})),a.d(e,"a",(function(){}));var i=function(){var t=this,e=t.$createElement,a=t._self._c||e;return a("v-uni-view",{staticClass:"home-page"},[a("v-uni-view",{staticClass:"p-main"},[a("v-uni-view",{staticClass:"login_title"},[t._v("福宝知多少")]),a("v-uni-view",{staticClass:"logim_imageBox"},[a("v-uni-image",{staticClass:"logim_image",attrs:{src:"/static/image/logo.png",mode:"widthFix"}})],1),a("v-uni-view",[a("v-uni-button",{staticClass:"login_btn",on:{click:function(e){arguments[0]=e=t.$handleEvent(e),t.goPage.apply(void 0,arguments)}}},[t._v("开始对话")])],1)],1)],1)},n=[]},b1e7:function(t,e,a){"use strict";a.r(e);var i=a("ac01"),n=a("c842");for(var o in n)["default"].indexOf(o)<0&&function(t){a.d(e,t,(function(){return n[t]}))}(o);a("25f3");var r=a("f0c5"),c=Object(r["a"])(n["default"],i["b"],i["c"],!1,null,"7e7ab0b8",null,!1,i["a"],void 0);e["default"]=c.exports},c842:function(t,e,a){"use strict";a.r(e);var i=a("f102"),n=a.n(i);for(var o in i)["default"].indexOf(o)<0&&function(t){a.d(e,t,(function(){return i[t]}))}(o);e["default"]=n.a},f102:function(t,e,a){"use strict";a("7a82"),Object.defineProperty(e,"__esModule",{value:!0}),e.default=void 0,a("14d9");var i={data:function(){return{title:"Hello"}},onLoad:function(){},methods:{goPage:function(){var t=uni.getStorageSync("user_phone");t?this.$router.push({path:"/pages/chat/chat"}):this.$router.push({path:"pages/login/login"})}}};e.default=i}}]);