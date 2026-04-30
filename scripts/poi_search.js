const https = require('https');
const fs = require('fs');
const path = require('path');

// 高德API配置
const AMAP_API_KEY = '4c1a066cf3f56778bd9c51127991ff76';
const AMAP_API_BASE = 'https://restapi.amap.com';

// 加载配置文件
function loadConfig() {
    const configPath = path.join(__dirname, 'config.json');
    try {
        const configData = fs.readFileSync(configPath, 'utf8');
        return JSON.parse(configData);
    } catch (err) {
        console.warn('无法读取配置文件，使用默认配置:', err.message);
        return {
            bounds: [118.16374, 24.52104, 118.17755, 24.51194],
            city: '厦门',
            adcode: ''
        };
    }
}

/**
 * 在指定区域内搜索POI
 * @param {string} keyword - 搜索关键词
 * @param {number[]} bounds - 搜索范围 [左下经度, 左下纬度, 右上经度, 右上纬度]
 * @returns {Promise<Array>} 搜索结果
 */
async function searchPOI(keyword, bounds, city = '厦门', adcode = '') {
    return new Promise((resolve, reject) => {
        const [x1, y1, x2, y2] = bounds;
        // 高德多边形搜索API格式：左下经度,左下纬度;右上经度,右上纬度
        const polygonStr = `${x1},${y1};${x2},${y2}`;
        
        let url = `${AMAP_API_BASE}/v3/place/polygon?` +
                   `key=${AMAP_API_KEY}` +
                   `&keywords=${encodeURIComponent(keyword)}` +
                   `&polygon=${polygonStr}` +
                   `&extensions=all` +
                   `&offset=20` +
                   `&page=1` +
                   `&output=JSON`;
        
        if (city) {
            url += `&city=${encodeURIComponent(city)}`;
        }
        
        if (adcode) {
            url += `&citylimit=true&adcode=${adcode}`;
        }
        
        https.get(url, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    if (result.status === '1' && result.pois) {
                        const pois = result.pois.map(poi => ({
                            id: poi.id,
                            name: poi.name,
                            address: poi.address,
                            location: poi.location, // 经纬度
                            pname: poi.pname, // 省
                            cityname: poi.cityname, // 市
                            adname: poi.adname, // 区
                            type: poi.type,
                            typecode: poi.typecode,
                            polyline: poi.polyline, // 轮廓坐标
                            pcode: poi.pcode,
                            citycode: poi.citycode,
                            adcode: poi.adcode
                        }));
                        resolve(pois);
                    } else {
                        reject(new Error(`API错误: ${result.info}`));
                    }
                } catch (err) {
                    reject(err);
                }
            });
        }).on('error', reject);
    });
}

/**
 * 通过POI ID获取详细边界信息
 * @param {string} poiId - POI ID
 * @returns {Promise<Object>} 边界信息
 */
async function getPOIBoundary(poiId) {
    return new Promise((resolve, reject) => {
        const url = `${AMAP_API_BASE}/v3/place/detail?` +
                   `key=${AMAP_API_KEY}` +
                   `&id=${poiId}` +
                   `&extensions=all` +
                   `&output=JSON`;
        
        https.get(url, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    if (result.status === '1' && result.pois && result.pois.length > 0) {
                        const poi = result.pois[0];
                        resolve({
                            id: poi.id,
                            name: poi.name,
                            location: poi.location,
                            // 尝试获取多边形边界，格式可能是polyline或polygon
                            boundary: poi.polyline || poi.polygon || '',
                            // 获取矩形边界
                            rectangle: poi.boundary || '',
                            // 获取详细地址
                            address: poi.address,
                            // 行政区划信息
                            pcode: poi.pcode,
                            citycode: poi.citycode,
                            adcode: poi.adcode
                        });
                    } else {
                        reject(new Error(`未找到POI详情`));
                    }
                } catch (err) {
                    reject(err);
                }
            });
        }).on('error', reject);
    });
}

/**
 * 解析边界坐标字符串
 * @param {string} boundaryStr - 边界字符串
 * @returns {Array} 坐标数组
 */
function parseBoundary(boundaryStr) {
    if (!boundaryStr) return [];
    
    // 可能的分隔符：| 或 ;
    const points = boundaryStr.split(/[|;]/);
    return points.map(point => {
        const [lng, lat] = point.split(',');
        return { lng: parseFloat(lng), lat: parseFloat(lat) };
    });
}

/**
 * 获取区域的边界框
 * @param {Array} coordinates - 坐标数组
 * @returns {Object} 边界框
 */
function getBoundingBox(coordinates) {
    if (coordinates.length === 0) return null;
    
    let minLng = coordinates[0].lng;
    let maxLng = coordinates[0].lng;
    let minLat = coordinates[0].lat;
    let maxLat = coordinates[0].lat;
    
    coordinates.forEach(coord => {
        minLng = Math.min(minLng, coord.lng);
        maxLng = Math.max(maxLng, coord.lng);
        minLat = Math.min(minLat, coord.lat);
        maxLat = Math.max(maxLat, coord.lat);
    });
    
    return {
        southwest: { lng: minLng, lat: minLat },
        northeast: { lng: maxLng, lat: maxLat },
        center: { lng: (minLng + maxLng) / 2, lat: (minLat + maxLat) / 2 }
    };
}

/**
 * 关键词扩展映射表 - 用于多轮搜索
 * 如果直接搜索不到结果，尝试使用扩展关键词
 */
const keywordExpansion = {
    '休息亭': ['五缘湾湿地公园-休息亭', '湿地公园', '凉亭'],
    '凉亭': ['五缘湾湿地公园-凉亭', '湿地公园', '休息亭'],
    '亭子': ['湿地公园', '五缘湾湿地公园-凉亭'],
    '观景亭': ['五缘湾湿地公园-凉亭', '湿地公园'],
};

/**
 * 执行多轮搜索 - 如果第一个关键词失败，尝试扩展关键词
 */
async function searchWithFallback(keyword, bounds, city, adcode) {
    // 首先尝试使用原始关键词
    let pois = await searchPOI(keyword, bounds, city, adcode);
    
    // 如果搜不到结果，尝试使用扩展关键词
    if (pois.length === 0 && keywordExpansion[keyword]) {
        const fallbackKeywords = keywordExpansion[keyword];
        console.log(`⚠ 未找到"${keyword}"的结果，尝试扩展关键词搜索...`);
        
        for (const fallback of fallbackKeywords) {
            console.log(`  → 尝试搜索: "${fallback}"`);
            pois = await searchPOI(fallback, bounds, city, adcode);
            
            if (pois.length > 0) {
                console.log(`  ✓ 使用关键词"${fallback}"搜到${pois.length}个结果`);
                break;
            }
        }
    }
    
    return pois;
}

/**
 * 主函数
 */
async function main() {
    const args = process.argv.slice(2);
    
    if (args.length < 1) {
        console.log('使用方法:');
        console.log('  node poi_search.js <关键词>');
        console.log('示例:');
        console.log('  node poi_search.js "中山路"');
        console.log('  node poi_search.js "医院"');
        console.log('  node poi_search.js "休息亭"  # 自动尝试扩展搜索');
        console.log('');
        console.log('可选参数:');
        console.log('  --adcode 行政区划代码');
        console.log('  --city 城市名');
        console.log('');
        console.log('配置文件 (config.json):');
        console.log('  bounds   搜索范围 [左下经度, 左下纬度, 右上经度, 右上纬度]');
        console.log('  city     城市名');
        console.log('  adcode   行政区划代码');
        console.log('');
        return;
    }

    const keyword = args[0];

    // 从配置文件加载默认配置
    const config = loadConfig();
    let bounds = config.bounds || [118.0, 24.4, 118.2, 24.5];
    let city = config.city || '厦门';
    let adcode = config.adcode || '';

    // 命令行参数可以覆盖配置文件
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--city' && args[i + 1]) {
            city = args[i + 1];
        } else if (args[i] === '--adcode' && args[i + 1]) {
            adcode = args[i + 1];
        }
    }
    
    console.log(`正在搜索: "${keyword}"`);
    console.log(`搜索范围: ${bounds}`);
    console.log(`城市: ${city}`);
    
    try {
        // 使用多轮搜索 - 如果第一个关键词失败，自动尝试扩展关键词
        const pois = await searchWithFallback(keyword, bounds, city, adcode);
        console.log(`找到 ${pois.length} 个结果`);
        
        // 直接使用搜索结果（高德Web服务API不返回边界信息，无需额外调用详情API）
        const results = pois.slice(0, 10).map(poi => {
            // 解析location为坐标对象
            const [lng, lat] = (poi.location || '').split(',').map(Number);
            return {
                id: poi.id,
                name: poi.name,
                location: poi.location,
                address: poi.address,
                pcode: poi.pcode,
                citycode: poi.citycode,
                adcode: poi.adcode,
                // 中心点坐标
                center: { lng, lat },
                // 边界相关字段保留但为空（API不返回）
                coordinates: [],
                boundingBox: null
            };
        });
        
        // 控制台输出摘要
        console.log('\n搜索结果摘要:');
        results.forEach((result, index) => {
            console.log(`\n${index + 1}. ${result.name}`);
            console.log(`   地址: ${result.address || '无'}`);
            console.log(`   坐标: ${result.location}`);
            console.log(`   中心点: ${result.center.lng}, ${result.center.lat}`);
        });
        
    } catch (error) {
        console.error('搜索失败:', error.message);
    }
}

// 运行主函数
if (require.main === module) {
    main();
}

module.exports = { searchPOI, getPOIBoundary, parseBoundary, getBoundingBox };