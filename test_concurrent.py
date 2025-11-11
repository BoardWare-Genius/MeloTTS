import asyncio
import aiohttp
import time
import statistics
import csv
from typing import List, Dict
from datetime import datetime

# ---------------- 基本配置 ----------------
BASE_URL = "http://10.6.14.130:5000/convert/tts"

REQUEST_TEMPLATE = {
    "text": "哇，你这个新买的T-shirt好cool啊！是哪个brand的？周末我们去新开的mall里那家Starbucks喝杯coffee吧？我听说他们的new season限定款Latte很OK。",
    "speaker_id": "ZH",
    "language": "ZH",
    "speed": "0.9"
}

DEFAULT_HEADERS = {"Content-Type": "application/json"}


# ---------------- 请求逻辑 ----------------
async def tts_request(session: aiohttp.ClientSession, request_id: int) -> float:
    """执行一次请求，返回耗时（秒）"""
    start = time.perf_counter()
    try:
        async with session.post(BASE_URL, json=REQUEST_TEMPLATE, headers=DEFAULT_HEADERS) as resp:
            await resp.read()
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
    except Exception as e:
        print(f"[请求 {request_id}] 出错: {e}")
        return -1
    return time.perf_counter() - start


# ---------------- 并发测试核心 ----------------
async def benchmark(concurrency: int, total_requests: int) -> Dict:
    """在指定并发下发起多次请求，统计性能指标"""
    timings = []
    errors = 0

    conn = aiohttp.TCPConnector(limit=0, force_close=False)
    timeout = aiohttp.ClientTimeout(total=None)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        sem = asyncio.Semaphore(concurrency)

        async def worker(i):
            nonlocal errors
            async with sem:
                t = await tts_request(session, i)
                if t > 0:
                    timings.append(t)
                else:
                    errors += 1

        tasks = [asyncio.create_task(worker(i)) for i in range(total_requests)]
        await asyncio.gather(*tasks)

    succ = len(timings)
    total_time = sum(timings)
    result = {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "successes": succ,
        "errors": errors,
    }

    if succ > 0:
        result.update({
            "min": min(timings),
            "max": max(timings),
            "avg": statistics.mean(timings),
            "median": statistics.median(timings),
            "qps": succ / total_time if total_time > 0 else 0
        })
    return result


# ---------------- CSV 写入 ----------------
def write_to_csv(filename: str, data: List[Dict]):
    """把测试结果写入 CSV 文件"""
    fieldnames = ["concurrency", "total_requests", "successes", "errors",
                  "min", "max", "avg", "median", "qps"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print(f"\n✅ 测试结果已保存到: {filename}")


# ---------------- 主流程 ----------------
async def run_tests(concurrency_list: List[int], total_requests: dict):
    print("开始压测接口:", BASE_URL)
    results = []
    for c in concurrency_list:
        print(f"\n=== 并发数: {c} ===")
        res = await benchmark(c, total_requests[c])
        results.append(res)

        print(f"请求总数: {res['total_requests']} | 成功: {res['successes']} | 失败: {res['errors']}")
        if "avg" in res:
            print(f"耗时 (s) → min={res['min']:.3f}, avg={res['avg']:.3f}, median={res['median']:.3f}, max={res['max']:.3f}")
            print(f"近似 QPS: {res['qps']:.2f}")
        else:
            print("所有请求均失败")

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_filename = f"tts_benchmark_{timestamp}.csv"
    write_to_csv(csv_filename, results)


if __name__ == "__main__":
    # 你可以根据机器能力调整这两个参数
    concurrency_list = [1, 5, 10, 20, 50, 100, 150, 200]  # 并发测试范围
    total_requests = {
        1: 50,
        5: 100,
        10: 200,
        20: 400,
        50: 1000,
        100: 2000,
        150: 3000,
        200: 4000,
        300: 6000,
        500: 10000
    }                                  # 每个并发等级下的请求数
    asyncio.run(run_tests(concurrency_list, total_requests))

# import asyncio
# import aiohttp
# import time
# import statistics
# from typing import List, Dict

# # 目标接口 URL 和请求体模板
# BASE_URL = "http://10.6.14.130:5000/convert/tts"

# # 你要请求的文本和参数
# REQUEST_TEMPLATE = {
#     "text": "哇，你这个新买的T-shirt好cool啊！是哪个brand的？周末我们去新开的mall里那家Starbucks喝杯coffee吧？我听说他们的new season限定款Latte很OK。",
#     # "text": "藤椅阁楼的尘埃在午后的光柱里缓缓飘浮，像时间的碎屑。我拨开蛛网，在杂物的最深处看见了它——那把老藤椅。椅背已经塌陷，藤条断裂处翘起，如同老人干裂的皮肤。我轻轻一碰，它便发出“吱呀”一声，像是从很远很远的过去传来的叹息。这声叹息把我拽回了三十年前的夏天。祖父总是占据着这把藤椅，仿佛那是他的王座。傍晚的风带着栀子花的香气，藤椅在祖父身下唱着有节奏的歌谣：“吱呀——吱呀——”像古老的摇篮曲。我趴在他膝头，数着他胡子里的白茬，听他用带着烟味的声音说：“这椅子啊，比你爸爸年纪都大。那时我不懂，一把破椅子有什么可珍贵的。直到祖父去世，父亲在藤椅前坐了整整一夜。月光透过窗格，把藤条的影子织成一张网，网住了父亲微微佝偻的背影。我看见他的手一遍遍抚摸着扶手——那里被祖父的手掌磨得油亮如玉，仿佛还能触到曾经的温度。如今，父亲也到了祖父当年的年纪。某个失眠的深夜，我走下楼梯，看见父亲在阳台的藤椅上睡着了。月光如水，把他的白发染得更加苍白。藤椅承着他发福的身体，每一次呼吸都伴随着细微的“吱呀”声。那一刻我突然明白，这把藤椅从来不只是家具，它是我们家族血脉流淌的河床，三代人的体温在上面重叠、交融。我决定修复这把藤椅。邻居陈爷爷是最后的藤匠，他教我如何将新藤在热水里泡软，如何沿着旧孔穿行，如何在断裂处打结续接。“修旧如旧，”他眯着眼睛说，“就像侍候老人，要懂它的脾气。”我的手指很快磨出了水泡，但当第一根新藤穿过旧孔，那种奇妙的连接让我心头一颤——我续上的不是藤条，是一段几乎中断的记忆。修复后的藤椅摆在书房角落，我不常坐，但喜欢看着它。阳光照进来时，新旧藤条交织出深深浅浅的影子，像一封用时光写就的家书。最奇妙的是它依然会“吱呀”作响，只是那声音不再苍凉，反而有种新生的欢快。昨天，三岁的女儿摇摇晃晃地爬上空着的藤椅，小手拍着扶手，口齿不清地学舌：“吱呀——吱呀——”我忽然泪流满面。原来传承如此简单——它不需要豪言壮语，只是一把老椅子继续承载新的重量，只是一首无词的歌谣被新的喉咙继续传唱。藤椅还在那里，“吱呀”声穿越三代人，细若游丝却从未断绝。我终于听懂——那不是木头与藤条的摩擦，而是时间流过生命河床的声音，温柔而固执，告诉我们：有些东西看似破旧，却比所有光鲜的事物都更接近永恒。",
#     "speaker_id": "ZH",
#     "language": "ZH",
#     "speed": "0.9"
# }

# # 如果接口还需要额外的 headers 或认证，你可以在这里加
# DEFAULT_HEADERS = {
#     "Content-Type": "application/json"
# }


# async def tts_request(session: aiohttp.ClientSession) -> float:
#     """
#     发起一次 TTS 请求，返回耗时（秒）。若失败则抛异常。
#     """
#     start = time.perf_counter()
#     async with session.post(BASE_URL, json=REQUEST_TEMPLATE, headers=DEFAULT_HEADERS) as resp:
#         # 你可以根据接口返回形式做不同处理，比如 .json() 或 .read()
#         data = await resp.read()
#         if resp.status != 200:
#             # 抛出异常以便上层捕获
#             raise RuntimeError(f"HTTP {resp.status}, body: {data[:200]!r}")
#     elapsed = time.perf_counter() - start
#     return elapsed


# async def benchmark(concurrency: int, total_requests: int) -> Dict:
#     """
#     并发地发 total_requests 个请求，每次最多 concurrency 个并发。
#     返回统计结果。
#     """
#     timings: List[float] = []
#     errors = 0

#     # 复用一个 session，提高效率
#     conn = aiohttp.TCPConnector(limit=0)  # limit=0 表示不限制连接数
#     timeout = aiohttp.ClientTimeout(total=None)  # 你也可以设置一个超时时间
#     async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
#         sem = asyncio.Semaphore(concurrency)

#         async def worker():
#             nonlocal errors
#             async with sem:
#                 try:
#                     t = await tts_request(session)
#                     timings.append(t)
#                 except Exception as e:
#                     errors += 1
#                     # 可选：打印或记录异常
#                     print("请求出错：", e)

#         tasks = [asyncio.create_task(worker()) for _ in range(total_requests)]
#         await asyncio.gather(*tasks)

#     succ = len(timings)
#     total_time = sum(timings) if timings else 0.0

#     result = {
#         "concurrency": concurrency,
#         "total_requests": total_requests,
#         "successes": succ,
#         "errors": errors,
#     }
#     if succ > 0:
#         result.update({
#             "min": min(timings),
#             "max": max(timings),
#             "avg": statistics.mean(timings),
#             "median": statistics.median(timings),
#             # 吞吐量：成功请求总数 / 总耗时（近似 QPS）
#             "qps": succ / total_time if total_time > 0 else None
#         })
#     return result


# async def run_tests(concurrency_list: List[int], total_requests: int):
#     """
#     针对不同的并发数做测试，输出每种并发数下的结果。
#     """
#     print("开始并发测试，目标接口：", BASE_URL)
#     for c in concurrency_list:
#         print(f"\n--- 并发 = {c} ---")
#         res = await benchmark(c, total_requests)
#         print("总请求：", res["total_requests"])
#         print("成功：", res["successes"], "失败：", res["errors"])
#         if "avg" in res:
#             print(f"耗时 min / avg / median / max = "
#                   f"{res['min']:.3f} / {res['avg']:.3f} / {res['median']:.3f} / {res['max']:.3f} 秒")
#             print(f"近似 QPS = {res['qps']:.2f}")
#         else:
#             print("所有请求都失败了")

# if __name__ == "__main__":
#     # 你可以调整这些参数
#     concurrency_list = [1, 5, 10, 20, 50, 100, 150, 200, 300, 400]     # 要试的并发数列表
#     total_requests = 100                      # 每个并发等级下总请求数

#     asyncio.run(run_tests(concurrency_list, total_requests))



# import asyncio
# import aiohttp
# import time
# from multiprocessing import Process, Queue, current_process, set_start_method
# import statistics
# from typing import Dict, List

# BASE_URL = "http://10.6.14.130:5000/convert/tts"
# REQUEST_TEMPLATE = {
#     "text": "哇，你这个新买的T-shirt好cool啊！是哪个brand的？周末我们去新开的mall里那家Starbucks喝杯coffee吧？我听说他们的new season限定款Latte很OK。",
#     "speaker_id": "ZH",
#     "language": "ZH",
#     "speed": "0.9"
# }
# DEFAULT_HEADERS = {
#     "Content-Type": "application/json"
# }

# def worker_process(task_queue: Queue, result_queue: Queue, concurrency: int):
#     """
#     子进程入口：从 task_queue 获取任务 (如请求数)，执行对应数量的异步 HTTP 请求，然后把统计结果放到 result_queue。
#     """
#     # 每个子进程可以打印自己的 PID
#     pid = current_process().pid
#     # 我们定义一个子进程内部的协程来跑异步请求
#     async def tts_request(session: aiohttp.ClientSession) -> float:
#         start = time.perf_counter()
#         async with session.post(BASE_URL, json=REQUEST_TEMPLATE, headers=DEFAULT_HEADERS) as resp:
#             data = await resp.read()
#             if resp.status != 200:
#                 raise RuntimeError(f"HTTP {resp.status}, body: {data[:200]!r}")
#         return time.perf_counter() - start

#     async def run_batch(num_requests: int):
#         timings: List[float] = []
#         errors = 0

#         conn = aiohttp.TCPConnector(limit=0)
#         timeout = aiohttp.ClientTimeout(total=None)
#         async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
#             sem = asyncio.Semaphore(concurrency)

#             async def one_req():
#                 nonlocal errors
#                 async with sem:
#                     try:
#                         t = await tts_request(session)
#                         timings.append(t)
#                     except Exception as e:
#                         errors += 1
#                         # 可选地记录错误 e

#             tasks = [asyncio.create_task(one_req()) for _ in range(num_requests)]
#             await asyncio.gather(*tasks)

#         # 返回一个 dict 统计
#         result = {
#             "pid": pid,
#             "concurrency": concurrency,
#             "num_requests": num_requests,
#             "successes": len(timings),
#             "errors": errors,
#         }
#         if timings:
#             result.update({
#                 "min": min(timings),
#                 "max": max(timings),
#                 "avg": statistics.mean(timings),
#                 "median": statistics.median(timings),
#                 "total_time": sum(timings)
#             })
#         return result

#     # 子进程主逻辑：不断从 task_queue 取任务，执行，然后把结果回传
#     while True:
#         try:
#             task = task_queue.get(block=True, timeout=5)
#         except Exception:
#             # 如果超时没拿到任务，可以退出（或 continue）
#             break
#         if task is None:
#             # 约定 None 表示退出信号
#             break
#         # task 预期是要跑多少请求
#         num_req = task.get("num_requests", 0)
#         # concurrency 可作为参数 task 传进来，也可以用全局 concurrency
#         coro = run_batch(num_req)
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#         result = loop.run_until_complete(coro)
#         loop.close()

#         result_queue.put(result)

# def multiprocess_benchmark(num_processes: int, concurrency_per_proc: int, requests_per_proc: int):
#     """
#     启动 num_processes 个子进程，每个子进程发 concurrency_per_proc 并发，做 requests_per_proc 请求。
#     最终合并所有子进程的统计。
#     """
#     # 在主进程里设置启动方式
#     try:
#         set_start_method("spawn")
#     except RuntimeError:
#         pass

#     task_queue = Queue()
#     result_queue = Queue()

#     procs = []
#     for i in range(num_processes):
#         p = Process(target=worker_process, args=(task_queue, result_queue, concurrency_per_proc))
#         p.start()
#         procs.append(p)

#     # 发任务给每个子进程
#     for _ in range(num_processes):
#         task_queue.put({"num_requests": requests_per_proc})
#     # 发退出信号
#     for _ in range(num_processes):
#         task_queue.put(None)

#     # 收集子进程结果
#     results = []
#     for _ in range(num_processes):
#         res = result_queue.get()
#         results.append(res)

#     # 等待子进程退出
#     for p in procs:
#         p.join()

#     # 合并统计
#     total_success = sum(r["successes"] for r in results if "successes" in r)
#     total_errors = sum(r["errors"] for r in results if "errors" in r)
#     all_timings = []
#     for r in results:
#         if "total_time" in r:
#             # 这里我们不能简单把 “总耗时” 相加作为基准，因为每个进程并行执行
#             # 但可以把每个进程内部的 timings（平均、分布）作为参考
#             pass

#     print("==== 各子进程结果 ====")
#     for r in results:
#         print(r)
#     print("==== 合并结果 ====")
#     print("总成功：", total_success, "总失败：", total_errors)
#     # 你可以根据需要计算一个“总体 QPS”估算

# if __name__ == "__main__":
#     # 参数示例
#     num_processes = 4
#     concurrency_per_proc = 20
#     requests_per_proc = 100

#     multiprocess_benchmark(num_processes, concurrency_per_proc, requests_per_proc)



# import asyncio
# import aiohttp
# import time
# import statistics
# from typing import List, Dict

# # ---------------- 基本配置 ----------------
# BASE_URL = "http://10.6.14.130:5000/convert/tts"

# REQUEST_TEMPLATE = {
#     "text": "哇，你这个新买的T-shirt好cool啊！是哪个brand的？周末我们去新开的mall里那家Starbucks喝杯coffee吧？",
#     "speaker_id": "ZH",
#     "language": "ZH",
#     "speed": 0.9
# }

# DEFAULT_HEADERS = {"Content-Type": "application/json"}

# # ---------------- 请求逻辑 ----------------
# async def tts_request(session: aiohttp.ClientSession, request_id: int) -> float:
#     """执行一次请求，返回耗时"""
#     start = time.perf_counter()
#     try:
#         async with session.post(BASE_URL, json=REQUEST_TEMPLATE, headers=DEFAULT_HEADERS) as resp:
#             await resp.read()  # 接口返回音频二进制
#             if resp.status != 200:
#                 raise RuntimeError(f"HTTP {resp.status}")
#     except Exception as e:
#         print(f"[请求 {request_id}] 出错: {e}")
#         return -1
#     return time.perf_counter() - start

# # ---------------- 并发测试核心 ----------------
# async def benchmark(concurrency: int, total_requests: int) -> Dict:
#     """在指定并发下发起多次请求，统计性能指标"""
#     timings = []
#     errors = 0

#     conn = aiohttp.TCPConnector(limit=0, force_close=False)
#     timeout = aiohttp.ClientTimeout(total=None)
#     async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
#         sem = asyncio.Semaphore(concurrency)

#         async def worker(i):
#             nonlocal errors
#             async with sem:
#                 t = await tts_request(session, i)
#                 if t > 0:
#                     timings.append(t)
#                 else:
#                     errors += 1

#         tasks = [asyncio.create_task(worker(i)) for i in range(total_requests)]
#         await asyncio.gather(*tasks)

#     succ = len(timings)
#     total_time = sum(timings)
#     result = {
#         "concurrency": concurrency,
#         "total_requests": total_requests,
#         "successes": succ,
#         "errors": errors,
#     }

#     if succ > 0:
#         result.update({
#             "min": min(timings),
#             "max": max(timings),
#             "avg": statistics.mean(timings),
#             "median": statistics.median(timings),
#             "qps": succ / total_time if total_time > 0 else 0
#         })
#     return result

# # ---------------- 主流程 ----------------
# async def run_tests(concurrency_list: List[int], total_requests: int):
#     print("开始压测接口:", BASE_URL)
#     for c in concurrency_list:
#         print(f"\n=== 并发数: {c} ===")
#         res = await benchmark(c, total_requests)
#         print(f"请求总数: {res['total_requests']} | 成功: {res['successes']} | 失败: {res['errors']}")
#         if "avg" in res:
#             print(f"耗时 (s) → min={res['min']:.3f}, avg={res['avg']:.3f}, median={res['median']:.3f}, max={res['max']:.3f}")
#             print(f"近似 QPS: {res['qps']:.2f}")
#         else:
#             print("所有请求均失败")

# if __name__ == "__main__":
#     concurrency_list = [1, 5, 10, 20, 50]  # 可调整
#     total_requests = 50                    # 每种并发下的请求总数
#     asyncio.run(run_tests(concurrency_list, total_requests))
