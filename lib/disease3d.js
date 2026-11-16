/* 识稼日报 · 病相立体图（真实模型版 v2）
 * 只加载 models/ 下由三维生成 AI（Meshy）建好的 GLB / GLTF。
 * 旧版的画布程序化模型（麦叶 / 茎秆 / 麦穗 + 手绘病斑）已整体移除：
 * 它初始化时默认可见，识别后没被关掉，会和真实模型叠在一起。
 * 现在某种病缺文件，就在画布里明说「尚未就位」，不再用假模型顶替。
 */
(function () {
    'use strict';

    if (!window.THREE) {
        console.warn('[病相3D] three.js 未加载');
        return;
    }

    var DISEASES = {
        /* ===== 小麦 ===== */
        tiaoxiu: { crop: '小麦', name: '小麦条锈病', tag: '条锈', note: '鲜黄色孢子堆沿叶脉排成一行行，远看像叶面上划了黄线。' },
        yexiu: { crop: '小麦', name: '小麦叶锈病', tag: '叶锈', note: '橙褐色孢子堆散生叶面，圆形的，大小不一，不成行。' },
        ganxiu: { crop: '小麦', name: '小麦秆锈病', tag: '秆锈', note: '深褐红色的疱状突起，长在茎秆和叶鞘上，个头最大。' },
        baifen: { crop: '小麦', name: '小麦白粉病', tag: '白粉', note: '叶面覆一层白色粉状霉层，擦一下能掉粉，后期变灰。' },
        chimei: { crop: '小麦', name: '小麦赤霉病', tag: '赤霉', note: '长在麦穗上，小穗基部冒出粉红色霉层，穗子发白枯死。' },
        wenku: { crop: '小麦', name: '小麦纹枯病', tag: '纹枯', note: '茎基部出现椭圆形褐色病斑，一圈套一圈像云纹，后期茎秆折倒。' },
        /* ===== 玉米 ===== */
        ym_daban: { crop: '玉米', name: '玉米大斑病', tag: '大斑', note: '叶片上拉出长梭形的灰褐大斑，顺着叶脉跑，严重时从下往上枯。' },
        ym_xiaoban: { crop: '玉米', name: '玉米小斑病', tag: '小斑', note: '叶片上密密的小椭圆斑，中间灰白、边上一圈褐，比大斑小得多。' },
        ym_xiu: { crop: '玉米', name: '玉米锈病', tag: '玉米锈', note: '叶面冒出肉桂色的小疱堆，一碰掉黄粉，抽雄前后最容易发。' },
        /* ===== 番茄 ===== */
        fq_zaoyi: { crop: '番茄', name: '番茄早疫病', tag: '早疫', note: '叶片上一圈套一圈的褐色轮纹斑，像个靶子，外头还带黄圈。' },
        fq_wanyi: { crop: '番茄', name: '番茄晚疫病', tag: '晚疫', note: '叶边叶尖先起暗绿水渍斑，潮天背面长白霉，一夜能毁一片。' },
        fq_huimei: { crop: '番茄', name: '番茄灰霉病', tag: '灰霉', note: '果子上糊一层灰褐绒毛霉，摸着软塌塌，专挑残花落瓣处下手。' },
        /* ===== 黄瓜 ===== */
        hg_shuangmei: { crop: '黄瓜', name: '黄瓜霜霉病', tag: '霜霉', note: '叶正面多角形黄褐斑，四面被叶脉框死，背面一层灰黑霉。' },
        hg_baifen: { crop: '黄瓜', name: '黄瓜白粉病', tag: '白粉', note: '叶面撒了一层白粉，越擦越明显，后头叶子发黄卷边。' },
        hg_jiaoban: { crop: '黄瓜', name: '黄瓜细菌性角斑病', tag: '角斑', note: '叶上多角形水渍褐斑，中间干裂出洞，穿孔是它的记号。' },
        /* ===== 水稻 ===== */
        sd_daowen: { crop: '水稻', name: '稻瘟病', tag: '稻瘟', note: '叶片上梭形病斑，两头尖中间灰白，穗颈一断就成白穗。' },
        sd_daoqu: { crop: '水稻', name: '稻曲病', tag: '稻曲', note: '谷粒变成墨绿色绒球，比正常谷粒大一圈，一穗上几粒就够呛。' },
        sd_baijieku: { crop: '水稻', name: '水稻白叶枯病', tag: '白叶枯', note: '叶尖叶缘起波纹状黄白条，顺着叶脉往下枯，像被开水烫过。' }
    };

    var ORDER = [
        'tiaoxiu', 'yexiu', 'ganxiu', 'baifen', 'chimei', 'wenku',
        'ym_daban', 'ym_xiaoban', 'ym_xiu',
        'fq_zaoyi', 'fq_wanyi', 'fq_huimei',
        'hg_shuangmei', 'hg_baifen', 'hg_jiaoban',
        'sd_daowen', 'sd_daoqu', 'sd_baijieku'
    ];

    var renderer, scene, camera, stage, canvas, floor, waitEl = null;
    var keyLight = null;        /* 主光；影子的取景框要跟着模型走 */
    var baseSpan = 0;           /* 模型在 zoom=1 时的最大跨距 */
    var shadowZoom = -1;        /* 上次给影子取景框用的缩放值 */
    var wraps = {};     /* key -> Group：已经下载好的真实模型 */
    var loading = {};   /* key -> true：正在下载 */
    var missing = {};   /* key -> true：四个候选路径全失败 */
    var active = null;  /* 当前摆在舞台上的那一个 */
    var current = null; /* 最近一次要求显示的病 */

    var dragging = false, lastX = 0, lastY = 0;
    var rotY = 0.14, rotX = 0.02, zoom = 1, targetZoom = 1;
    var appearT = 1, autoSpin = true, lastPinch = 0;
    var raf = null, inited = false, onScreen = true;

    /* ============ 画布里的状态字 ============ */
    function setWait(text) {
        if (!stage) return;
        if (!waitEl) {
            waitEl = document.createElement('div');
            waitEl.style.cssText = 'position:absolute;left:0;right:0;top:50%;' +
                'transform:translateY(-50%);text-align:center;font-size:12px;letter-spacing:2px;' +
                'color:#8c8375;pointer-events:none;z-index:2;' +
                'font-family:"Songti SC","SimSun",serif;';
            stage.appendChild(waitEl);
        }
        waitEl.textContent = text;
        waitEl.style.display = 'block';
    }

    function clearWait() {
        if (waitEl) waitEl.style.display = 'none';
    }

    /* ============ 按相机视野适配：竖占 86%、横不超过 88%，取小保证不裁 ============ */
    function fitToStage(obj) {
        var box0 = new THREE.Box3().setFromObject(obj);
        var size = box0.getSize(new THREE.Vector3());

        /* 画布长宽比：桌面宽舞台约 4.0，手机竖屏约 1.3 */
        var aspect = 1;
        if (stage) {
            var wpx = stage.clientWidth || 0, hpx = stage.clientHeight || 0;
            if (wpx > 0 && hpx > 0) aspect = wpx / hpx;
        }
        var dist = (camera && camera.position) ? camera.position.z : 5;
        var viewH = 2 * dist * Math.tan(20 * Math.PI / 180);   /* FOV 40°，半角 20° */
        var viewW = viewH * aspect;

        /* 竖屏画布碰上横长的叶片（玉米、水稻）：把叶片转 90° 立起来。
           不转的话铺满宽度后高度只剩一成，成了一条细缝。 */
        if (aspect < 1.8 && size.x > size.y * 2.0) {
            obj.rotation.z = Math.PI / 2;
            var tmp = size.x;
            size.x = size.y;
            size.y = tmp;
        }

        var scY = viewH * 0.86 / Math.max(size.y, 0.0001);
        var scX = viewW * 0.88 / Math.max(size.x, size.z, 0.0001);
        var sc = Math.min(scY, scX);
        obj.scale.multiplyScalar(sc);

        /* 转完、缩完再量一次包围盒重新居中，保证稳稳落在画面正中 */
        var box1 = new THREE.Box3().setFromObject(obj);
        var c1 = box1.getCenter(new THREE.Vector3());
        obj.position.sub(c1);
    }

    /* ============ 落影地面挪到模型脚下 ============ */
    function footToFloor(wrap) {
        if (!floor) return;
        var box = new THREE.Box3().setFromObject(wrap);
        floor.position.y = box.min.y - 0.04;
        /* 记下模型真实跨距，影子的取景框按它撑开，不再用写死的 ±3.6 */
        var size = box.getSize(new THREE.Vector3());
        baseSpan = Math.max(size.x, size.y, size.z);
        shadowZoom = -1;
        updateShadowFrame(1);
    }

    /* 影子的取景框跟着模型大小和缩放走：
       横长的玉米叶片有十几个单位宽，原来的固定范围只盖住中间一截，
       影子在两头断掉，看着像穿进了模型里。 */
    function updateShadowFrame(z) {
        if (!keyLight || baseSpan <= 0) return;
        if (Math.abs(z - shadowZoom) < 0.08) return;
        shadowZoom = z;
        var r = baseSpan * z * 1.15 + 1.0;   /* 留出影子沿光线拉长的余量 */
        var c = keyLight.shadow.camera;
        c.left = -r; c.right = r; c.top = r; c.bottom = -r;
        c.near = 0.2; c.far = r * 3 + 12;
        c.updateProjectionMatrix();
    }

    /* ============ 下载真实模型 ============ */
    function loadModel(key) {
        if (wraps[key] || loading[key] || missing[key]) return;
        if (!THREE.GLTFLoader) {
            missing[key] = true;
            if (current === key) setWait('三维加载器缺失，无法载入模型');
            return;
        }
        loading[key] = true;
        var def = DISEASES[key];
        var loader = new THREE.GLTFLoader();
        var MODEL_VER = '?v=20261116a';
        var candidates = [
            'models/' + encodeURIComponent(def.name) + '.glb' + MODEL_VER,
            'models/' + encodeURIComponent(def.name) + '.gltf' + MODEL_VER,
            'models/' + encodeURIComponent(def.tag) + '.glb' + MODEL_VER,
            'models/' + encodeURIComponent(def.tag) + '.gltf' + MODEL_VER
        ];
        function tryNext(i) {
            if (i >= candidates.length) {
                loading[key] = false;
                missing[key] = true;
                if (current === key) setWait('这一种病害的立体模型尚未就位');
                return;
            }
            loader.load(candidates[i], function (gltf) {
                var obj = gltf.scene || (gltf.scenes && gltf.scenes[0]);
                if (!obj) { tryNext(i + 1); return; }
                obj.traverse(function (o) {
                    if (o.isMesh) {
                        o.castShadow = true;
                        /* 叶片是薄壁不闭合的壳，自己接收自己的影子会出黑条，
                           看着像表面被划破。标本只往外投影子，不接自影子。 */
                        o.receiveShadow = false;
                    }
                });
                fitToStage(obj);
                var wrap = new THREE.Group();
                wrap.add(obj);
                wrap.visible = false;
                scene.add(wrap);
                wraps[key] = wrap;
                loading[key] = false;
                if (current === key) present(key);
            }, undefined, function () { tryNext(i + 1); });
        }
        tryNext(0);
    }

    /* ============ 把已加载的模型摆上舞台 ============ */
    function present(key) {
        var w = wraps[key];
        if (!w) return;
        if (active && active !== w) active.visible = false;
        w.visible = true;
        w.scale.setScalar(1);
        w.position.set(0, 0, 0);
        w.rotation.set(0, 0, 0);
        active = w;
        footToFloor(w);
        clearWait();
        targetZoom = 1;
        if (appearT >= 1) zoom = 1;
    }

    /* ============ 初始化 ============ */
    function initScene(container) {
        stage = container;
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.1;
        if (THREE.sRGBEncoding !== undefined) renderer.outputEncoding = THREE.sRGBEncoding;

        canvas = renderer.domElement;
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.display = 'block';
        canvas.style.cursor = 'grab';
        container.appendChild(canvas);

        scene = new THREE.Scene();

        camera = new THREE.PerspectiveCamera(40, 1, 0.1, 40);
        camera.position.set(0, 0, 5.0);
        camera.lookAt(0, 0, 0);

        /* 光：暖主光投软影，冷补光提层次。
           主光抬高、往正上方收一点，影子就短、聚在脚下；
           原来那个斜长条拖出去老远，是画面里最丑的一块。 */
        scene.add(new THREE.HemisphereLight(0xfff7e0, 0x3a3225, 0.55));
        keyLight = new THREE.DirectionalLight(0xffefc8, 0.92);
        keyLight.position.set(1.7, 3.9, 1.9);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.set(2048, 2048);
        keyLight.shadow.camera.near = 0.2;
        keyLight.shadow.camera.far = 20;
        keyLight.shadow.bias = -0.0005;
        if (keyLight.shadow.normalBias !== undefined) keyLight.shadow.normalBias = 0.02;
        scene.add(keyLight);
        var fill = new THREE.DirectionalLight(0xd9e4ff, 0.24);
        fill.position.set(-3, -1.6, 2.4);
        scene.add(fill);

        /* 纸面：只接影子，不遮背景 */
        floor = new THREE.Mesh(
            new THREE.PlaneGeometry(26, 26),
            new THREE.ShadowMaterial({ opacity: 0.26 })
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -1.42;
        floor.receiveShadow = true;
        scene.add(floor);

        bindPointer(container);
        sizeToStage();
        inited = true;

        if (window.ResizeObserver) {
            new ResizeObserver(function () { sizeToStage(); }).observe(container);
        }
        if ('IntersectionObserver' in window) {
            new IntersectionObserver(function (entries) {
                onScreen = entries[0].isIntersecting;
            }, { threshold: 0.05 }).observe(container);
        }
        window.addEventListener('resize', sizeToStage);
        loop();
    }

    function sizeToStage() {
        if (!renderer || !stage) return;
        var w = stage.clientWidth || 600;
        var h = stage.clientHeight || 340;
        if (h < 10 || w < 10) return;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }

    /* ============ 交互：拖动旋转、滚轮缩放、双指捏合 ============ */
    function bindPointer(el) {
        el.addEventListener('pointerdown', function (e) {
            dragging = true;
            lastX = e.clientX; lastY = e.clientY;
            if (el.setPointerCapture) {
                try { el.setPointerCapture(e.pointerId); } catch (err) { }
            }
            if (canvas) canvas.style.cursor = 'grabbing';
        });
        el.addEventListener('pointermove', function (e) {
            if (!dragging) return;
            var dx = e.clientX - lastX, dy = e.clientY - lastY;
            lastX = e.clientX; lastY = e.clientY;
            rotY += dx * 0.008;
            rotX = Math.max(-0.55, Math.min(0.55, rotX + dy * 0.006));
        });
        function end(e) {
            dragging = false;
            if (canvas) canvas.style.cursor = 'grab';
            if (el.releasePointerCapture && e && e.pointerId !== undefined) {
                try { el.releasePointerCapture(e.pointerId); } catch (err) { }
            }
        }
        el.addEventListener('pointerup', end);
        el.addEventListener('pointerleave', end);
        el.addEventListener('pointercancel', end);

        el.addEventListener('wheel', function (e) {
            e.preventDefault();
            targetZoom = Math.max(0.55, Math.min(2.1, targetZoom - e.deltaY * 0.0016));
        }, { passive: false });

        el.addEventListener('touchmove', function (e) {
            if (e.touches && e.touches.length === 2) {
                var dx = e.touches[0].clientX - e.touches[1].clientX;
                var dy = e.touches[0].clientY - e.touches[1].clientY;
                var dist = Math.sqrt(dx * dx + dy * dy);
                if (lastPinch > 0) {
                    targetZoom = Math.max(0.55, Math.min(2.1, targetZoom * (dist / lastPinch)));
                }
                lastPinch = dist;
                e.preventDefault();
            } else {
                lastPinch = 0;
            }
        }, { passive: false });
    }

    /* ============ 出场缓动：先慢后快，落定时轻微回弹 ============ */
    function appearEase(t) {
        if (t >= 1) return 1;
        var p = 1 - Math.pow(1 - t, 3.2);
        return p + 0.06 * Math.sin(t * Math.PI * 3) * (1 - t);
    }

    /* ============ 动画循环 ============ */
    function loop() {
        raf = requestAnimationFrame(loop);
        if (!renderer || !onScreen) return;
        if (autoSpin && !dragging) rotY += 0.0036;
        zoom += (targetZoom - zoom) * 0.12;

        var grp = active;
        if (grp) {
            if (appearT < 1) {
                appearT = Math.min(1, appearT + 0.022);
                var k = appearEase(appearT);
                grp.scale.setScalar(zoom * (0.14 + 0.86 * k));
                grp.position.y = -2.2 * (1 - k);
                grp.rotation.set(rotX + 0.9 * (1 - k) * 0.35, rotY, 0);
            } else {
                grp.scale.setScalar(zoom);
                grp.position.y = 0;
                grp.rotation.set(rotX, rotY, 0);
                updateShadowFrame(zoom);
            }
        }
        renderer.render(scene, camera);
    }

    /* ============ 对外接口 ============ */
    var api = {
        init: function (containerId) {
            var el = document.getElementById(containerId);
            if (!el || inited) return;
            initScene(el);
        },
        show: function (key, opts) {
            if (!DISEASES[key] || !inited) return;
            current = key;
            if (opts && opts.appear) { appearT = 0; zoom = 0.86; }
            else { appearT = 1; zoom = 1; }

            if (wraps[key]) {
                present(key);
            } else if (missing[key]) {
                if (active) active.visible = false;
                active = null;
                setWait('这一种病害的立体模型尚未就位');
            } else {
                if (active) active.visible = false;
                active = null;
                setWait('模型载入中…');
                loadModel(key);
            }

            autoSpin = (opts && opts.spin === false) ? false : true;
        },
        pick: function (name) {
            if (!name) return null;
            var n = String(name).replace(/[\uFF08\uFF09()\s\u00b7]/g, '');
            var k, d, best = null, bestLen = 0;
            /* 1) 完整病名：取最长命中，避免「锈病」吃掉「条锈病」 */
            for (k in DISEASES) {
                d = DISEASES[k];
                if (n.indexOf(d.name) >= 0 && d.name.length > bestLen) {
                    best = k; bestLen = d.name.length;
                }
            }
            if (best) return best;
            /* 2) 作物名 + 病名关键字 */
            for (k in DISEASES) {
                d = DISEASES[k];
                var cropHit = n.indexOf(d.crop) >= 0 || (d.crop === '水稻' && n.indexOf('稻') >= 0);
                if (cropHit && n.indexOf(d.tag) >= 0) return k;
            }
            /* 3) 只给病名：唯一命中才认，有歧义就不立模型，免得认错 */
            var hits = [];
            for (k in DISEASES) {
                if (n.indexOf(DISEASES[k].tag) >= 0) hits.push(k);
            }
            return hits.length === 1 ? hits[0] : null;
        },
        info: DISEASES,
        order: ORDER
    };
    window.BingXiang3D = api;
})();
