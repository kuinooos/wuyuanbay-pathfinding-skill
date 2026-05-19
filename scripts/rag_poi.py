import json
import time
import hashlib
from pymilvus import MilvusClient
from dotenv import load_dotenv
import pandas as pd
import logging
from openai import OpenAI
import os
import re
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

embedding_name = "bge-m3"
embedding_url = "http://36.212.131.89:18001/v1"
embedding_dimension = 1024

# cd /home/jfcf/.hermes/skills/car-toolv1.0.1
# pip install pymilvus python-dotenv pandas openai   # 安装依赖
# python scripts/rag_poi.py seed                       # 插入预设数据
# python scripts/rag_poi.py seed --reload              # 清空后重新插入
# python scripts/rag_poi.py query 五缘湾湿地公园        # 查询

class RAGManager():

    def __init__(self):
        super().__init__()

        logger.info("init embedding...")
        self.openai_client = OpenAI(api_key="111", base_url=embedding_url)
        logger.info("init embedding success")

        logger.info("init Milvus...")
        self.client = MilvusClient("http://36.212.131.89:19530", db_name="car_tool")
        self.collection_name = "geo_locations"
        self.init_collection(reload=False)
        logger.info("init Milvus success")

    def add_data(self, location_name, latitude, longitude, desc):
        """
        向Milvus集合中插入地理位置向量数据

        Args:
            location_name (str): 地点名称
            latitude (str): 纬度坐标
            longitude (str): 经度坐标
            desc (str): 地点描述信息

        Returns:
            None
        """
        logger.info(f"====向 {self.collection_name} 中插入向量数据 name:{location_name} latitude:{latitude} longitude:{longitude} desc:{desc}====")

        vectors = self.openai_client.embeddings.create(
            model=embedding_name,
            input=[f"{location_name}-{desc}"]
        )

        data = [{"idx": f"{latitude}+{longitude}",
                "desc": desc,
                "name": location_name,
                "latitude": latitude,
                "longitude": longitude,
                "vector": vectors.data[0].embedding
                 }]

        self.client.insert(collection_name=self.collection_name, data=data)
        logger.info(f"向 {self.collection_name} 中插入向量数据成功")

    def get_datas(self, subject_keys, limit=5, radius=0.4):
        """
        基于语义相似度搜索地理位置数据，只返回置信度高于 radius 的结果。

        Args:
            subject_keys (list[str]): 查询关键词列表，用于生成查询向量
            limit (int):             最多返回条数
            radius (float):          相似度阈值（仅返回 score > radius 的结果）

        Returns:
            pd.DataFrame: 包含查询结果的数据框，包含以下列：
                - name: 地点名称
                - latitude: 纬度坐标
                - longitude: 经度坐标
                - desc: 地点描述
                - score: 相似度分数
        """
        response = self.openai_client.embeddings.create(
            model=embedding_name,
            input=subject_keys
        )
        query_vectors = [data.embedding for data in response.data]

        res = self.client.search(
            collection_name=self.collection_name,
            data=query_vectors,
            limit=limit,
            search_params={"radius": radius},
            output_fields=["name", "latitude", "longitude", "desc"],
        )

        infos = [item['entity'] for sublist in res for item in sublist]
        distances = [item['distance'] for sublist in res for item in sublist]
        df = pd.DataFrame(infos)
        df["score"] = distances
        return df

    def init_collection(self, reload):

        if self.client.has_collection(collection_name=self.collection_name) and reload:
            self.client.drop_collection(self.collection_name)

        if not self.client.has_collection(collection_name=self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                primary_field_name="idx",
                max_length=28,
                id_type="string",
                vector_field_name="vector",
                dimension=embedding_dimension,
            )

    def add_landmark(self, landmark_name: str, poi: list | None = None, category: str = ""):
        """插入地标向量数据（参照 rag.py 的 add_data 逻辑）。

        Args:
            landmark_name: 地标名称
            poi:          坐标 [lng, lat]
            category:     类别（landmark / toilet 等）
        """
        if poi:
            lng, lat = poi[0], poi[1]
            desc = f"category:{category}" if category else ""
        else:
            lat, lng = "", ""
            desc = ""
        text_for_embedding = f"{landmark_name}-{desc}"
        vectors = self.openai_client.embeddings.create(
            model=embedding_name,
            input=[text_for_embedding]
        )
        idx = hashlib.sha1(f"{lat}+{lng}".encode("utf-8")).hexdigest()[:20] if lat and lng else landmark_name
        data = [{
            "idx": idx,
            "name": landmark_name,
            "latitude": str(lat),
            "longitude": str(lng),
            "desc": desc,
            "vector": vectors.data[0].embedding
        }]
        try:
            self.client.insert(collection_name=self.collection_name, data=data)
        except Exception:
            self.client.upsert(collection_name=self.collection_name, data=data)
        logger.info(f"地标 '{landmark_name}' 已写入向量库")

    def get_poi_by_landmark(self, landmark_name: str, topk: int = 3):
        """通过语义搜索查询地标，返回匹配度最高的 topk 个结果。"""
        try:
            df = self.get_datas([landmark_name])
            if df.empty:
                return None
            results = []
            for _, row in df.head(topk).iterrows():
                lat = row.get("latitude", "")
                lng = row.get("longitude", "")
                if lat and lng:
                    results.append({
                        "name": row.get("name", ""),
                        "poi": [float(lng), float(lat)],
                        "score": round(row.get("score", 0), 4),
                    })
            return results if results else None
        except Exception:
            return None

    # ───────────────────────────── 预设数据加载 ─────────────────────────────

PRESET_DATA_PATH = os.path.join(os.path.dirname(__file__), "preset_data.json")


def load_preset_data() -> list:
    """从 preset_data.json 加载预设数据列表。"""
    if not os.path.exists(PRESET_DATA_PATH):
        logger.warning(f"预设数据文件不存在: {PRESET_DATA_PATH}")
        return []
    with open(PRESET_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("presets", [])


def seed_all(rag: RAGManager, reload: bool = False):
    """将所有已知地标和厕所预设写入向量数据库。

    Args:
        rag:    RAGManager 实例
        reload: 是否先清空集合再写入
    """
    if reload:
        rag.init_collection(reload=True)
        logger.info("集合已重建")

    presets = load_preset_data()
    for item in presets:
        rag.add_landmark(
            item["name"],
            poi=item.get("poi"),
            category=item.get("category", ""),
        )

    logger.info(f"播种完成，共 {len(presets)} 条预设数据")


def query_cli(rag: RAGManager, name: str):
    """CLI 查询：输出匹配度最高的 3 个地标。"""
    results = rag.get_poi_by_landmark(name)
    if results:
        print(f"查询「{name}」匹配度最高的 {len(results)} 个结果:\n")
        for i, r in enumerate(results, 1):
            print(f"  #{i}  {r['name']} → 坐标: {r['poi']}  (score: {r['score']})")
        print(f"\nJSON: {json.dumps(results, ensure_ascii=False)}")
    else:
        print(f"未知地标: {name}")
        print(f"JSON: {json.dumps({'name': name, 'found': False}, ensure_ascii=False)}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/rag_poi.py seed [--reload]   # 播种地标数据到向量库")
        print("  python scripts/rag_poi.py query <地标名>    # 查询地标对应的坐标")
        sys.exit(1)

    rag = RAGManager()

    cmd = sys.argv[1]

    if cmd == "seed":
        reload_flag = "--reload" in sys.argv
        seed_all(rag, reload=reload_flag)
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("[错误] 请指定地标名称，如: python scripts/rag_poi.py query 64号楼")
            sys.exit(1)
        query_name = " ".join(sys.argv[2:])  # 支持多词地名
        query_cli(rag, query_name)
    else:
        print(f"[错误] 未知命令: {cmd}")
        print("可用命令: seed, query")
        sys.exit(1)
