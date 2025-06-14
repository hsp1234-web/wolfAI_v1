import aiosqlite
import logging
import os
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class DataAccessLayer:
    """
    資料存取層 (DataAccessLayer) 類別。
    負責應用程式與 SQLite 資料庫之間的所有互動，包括資料的儲存、查詢和管理。
    它管理兩種主要的資料實體：報告 (reports) 和提示詞範本 (prompt_templates)。
    """
    def __init__(self, reports_db_path: str, prompts_db_path: str):
        """
        初始化 DataAccessLayer。

        Args:
            reports_db_path (str): 報告資料庫的檔案路徑。
            prompts_db_path (str): 提示詞範本資料庫的檔案路徑。
        """
        self.reports_db_path = reports_db_path
        self.prompts_db_path = prompts_db_path
        logger.info(
            f"DataAccessLayer 配置使用報告資料庫於: '{self.reports_db_path}' 及提示詞資料庫於: '{self.prompts_db_path}'.",
            extra={"props": {"service_name": "DataAccessLayer", "status": "configured", "reports_db": reports_db_path, "prompts_db": prompts_db_path}}
        )

    async def _execute_query(self, db_path: str, query: str, params: tuple = (), fetch_one=False, fetch_all=False, commit=False):
        """
        執行一個 SQL 查詢。

        這是一個私有的輔助方法，用於處理所有資料庫查詢的執行、錯誤處理和資源管理。
        它能夠執行查詢、提取單筆或多筆結果，以及提交事務。

        Args:
            db_path (str): 目標資料庫的檔案路徑。
            query (str): 要執行的 SQL 查詢語句。
            params (tuple, optional): 查詢的參數。預設為空元組。
            fetch_one (bool, optional): 是否只提取第一筆結果。預設為 False。
            fetch_all (bool, optional): 是否提取所有結果。預設為 False。
            commit (bool, optional): 是否在執行查詢後提交事務。預設為 False。
                                     如果為 True 且查詢是 INSERT，則返回 last_insert_rowid()。

        Returns:
            Optional[Any]: 根據操作類型返回不同的結果。
                           - 如果 commit 為 True 且是 INSERT 語句, 返回插入的 rowid。
                           - 如果 fetch_one 為 True, 返回單筆查詢結果 (aiosqlite.Row) 或 None。
                           - 如果 fetch_all 為 True, 返回多筆查詢結果 (List[aiosqlite.Row]) 或空列表。
                           - 其他情況返回 None。

        Raises:
            Exception: 如果在查詢執行過程中發生錯誤，會重新引發該異常。
        """
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"資料庫目錄 '{db_dir}' 不存在，已創建。", extra={"props": {"db_path": db_path, "action": "create_directory"}})
            except Exception as e_mkdir:
                logger.error(f"創建資料庫目錄 '{db_dir}' 失敗: {e_mkdir}", exc_info=True, extra={"props": {"db_path": db_path, "error": str(e_mkdir)}})
                raise # Re-raise if directory creation is critical

        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(query, params)
                if commit:
                    await db.commit()
                    # 對於 INSERT 操作，嘗試返回最後插入的行的 ID
                    if query.strip().upper().startswith("INSERT"):
                        id_cursor = await db.execute("SELECT last_insert_rowid()")
                        last_id_row = await id_cursor.fetchone()
                        await id_cursor.close()
                        return last_id_row[0] if last_id_row else None
                    return None # 對於其他提交操作 (如 UPDATE, DELETE)，不返回特定值
                if fetch_one:
                    result = await cursor.fetchone()
                    await cursor.close()
                    return result
                if fetch_all:
                    result = await cursor.fetchall()
                    await cursor.close()
                    return result
                await cursor.close() # 確保游標在不提取數據時也被關閉
                return None
        except Exception as e_query:
            # Add context to errors happening during query execution
            logger.error(
                f"執行資料庫查詢失敗。DB: '{db_path}', Query: '{query[:100]}...' (參數: {params})", # Log first 100 chars of query
                exc_info=True,
                extra={"props": {"db_path": db_path, "query_snippet": query[:100], "params": str(params), "error": str(e_query)}}
            )
            raise # Re-raise to be handled by calling method

    async def initialize_databases(self):
        """
        初始化所有必要的資料庫和表。
        如果表已存在，則此操作不會產生任何影響。
        """
        await self._create_reports_table()
        await self._create_prompts_table()
        logger.info("資料庫初始化完成 (如果需要)。", extra={"props": {"operation": "initialize_databases", "status": "completed"}})

    async def _create_reports_table(self):
        """
        在報告資料庫中創建 'reports' 表 (如果它尚不存在)。
        該表用於儲存已處理報告的相關資訊。
        """
        query = """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            content TEXT,
            source_path TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            metadata TEXT,
            analysis_json TEXT
        );
        """
        await self._execute_query(self.reports_db_path, query, commit=True)
        logger.info(f"'reports' 表已在 '{self.reports_db_path}' 中確認/創建。", extra={"props": {"db_table": "reports", "db_path": self.reports_db_path}})

    async def _create_prompts_table(self):
        """
        在提示詞資料庫中創建 'prompt_templates' 表 (如果它尚不存在)。
        該表用於儲存使用者定義的提示詞範本。
        """
        query = """
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            template_text TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self._execute_query(self.prompts_db_path, query, commit=True)
        logger.info(f"'prompt_templates' 表已在 '{self.prompts_db_path}' 中確認/創建。", extra={"props": {"db_table": "prompt_templates", "db_path": self.prompts_db_path}})

    async def insert_report_data(self, original_filename: str, content: Optional[str],
                                 source_path: str, metadata: Optional[Dict[str, Any]] = None,
                                 status: str = '已擷取待處理') -> Optional[int]:
        """
        將新的報告資料插入到 'reports' 資料庫。

        Args:
            original_filename (str): 報告的原始檔案名稱。
            content (Optional[str]): 報告的文本內容 (可能為 None，如果內容尚未提取或不適用)。
            source_path (str): 報告的來源路徑 (例如，在 Google Drive 中的路徑)。
            metadata (Optional[Dict[str, Any]], optional): 關於報告的附加元數據 (JSON 可序列化字典)。預設為 None。
            status (str, optional): 報告的初始狀態。預設為 '已擷取待處理'。

        Returns:
            Optional[int]: 如果插入成功，返回新報告的 ID；否則返回 None。
        """
        metadata_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
        query = "INSERT INTO reports (original_filename, content, source_path, metadata, status) VALUES (?, ?, ?, ?, ?)"
        log_props = {"original_filename": original_filename, "source_path": source_path, "status": status, "operation": "insert_report"}
        try:
            last_row_id = await self._execute_query(self.reports_db_path, query,
                                                (original_filename, content, source_path, metadata_str, status),
                                                commit=True)
            logger.info(
                f"新報告 '{original_filename}' 已插入到 reports 資料庫，ID: {last_row_id}，狀態: '{status}'。",
                extra={"props": {**log_props, "report_id": last_row_id, "db_operation_status": "success"}}
            )
            return last_row_id
        except Exception as e: # Catch errors re-raised from _execute_query
            logger.error(
                f"插入報告 '{original_filename}' 失敗: {e}", exc_info=False, # exc_info=False because _execute_query already logged it with True
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}} # Log the summarized error
            )
            return None

    async def get_report_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        """
        根據指定的 ID 從資料庫中檢索單個報告。

        Args:
            report_id (int): 要檢索的報告的 ID。

        Returns:
            Optional[Dict[str, Any]]: 如果找到報告，則返回包含報告資料的字典 (欄位名作為鍵)；
                                     否則返回 None。
        """
        query = "SELECT id, original_filename, content, source_path, processed_at, status, metadata, analysis_json FROM reports WHERE id = ?"
        try:
            async with aiosqlite.connect(self.reports_db_path) as db:
                db.row_factory = aiosqlite.Row # 使結果可以通過欄位名訪問
                cursor = await db.execute(query, (report_id,))
                row = await cursor.fetchone()
                await cursor.close()
            if row:
                report_data = dict(row)
                # 如果 metadata 或 analysis_json 是 JSON 字串，可以選擇在此處解析它們
                # 但通常 DAL 返回原始資料庫值，由服務層或調用者處理反序列化
                return report_data
            return None
        except Exception as e:
            logger.error(f"查詢報告 ID {report_id} 失敗: {e}", exc_info=True, extra={"props": {"report_id": report_id, "operation": "get_report_by_id", "error": str(e)}})
            return None


    async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
        """
        更新指定報告的狀態，並可選擇性地更新其處理後的內容。

        Args:
            report_id (int): 要更新的報告的 ID。
            status (str): 報告的新狀態。
            processed_content (Optional[str], optional): 報告處理後的文本內容。如果為 None，則不更新內容。預設為 None。

        Returns:
            bool: 如果更新成功，返回 True；否則返回 False。
        """
        fields_to_update = {"status": status}
        if processed_content is not None:
            fields_to_update["content"] = processed_content
        query_set_parts = [f"{field} = ?" for field in fields_to_update.keys()]
        query_params = list(fields_to_update.values())
        query_params.append(report_id)
        query = f"UPDATE reports SET {', '.join(query_set_parts)}, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        log_props = {"report_id": report_id, "new_status": status, "operation": "update_report_status"}
        try:
            await self._execute_query(self.reports_db_path, query, tuple(query_params), commit=True)
            logger.info(
                f"報告 ID {report_id} 的狀態已更新為 '{status}'。",
                extra={"props": {**log_props, "db_operation_status": "success"}}
            )
            return True
        except Exception as e:
            logger.error(
                f"更新報告 ID {report_id} 狀態失敗: {e}", exc_info=False, # _execute_query logs with exc_info=True
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def update_report_analysis(self, report_id: int, analysis_data: str, status: str) -> bool:
        """
        更新指定報告的 AI 分析結果 (JSON 字串) 和狀態。

        Args:
            report_id (int): 要更新的報告的 ID。
            analysis_data (str): AI 分析結果的 JSON 字串表示。
            status (str): 報告在分析後的新狀態 (例如，'分析完成', '分析失敗')。

        Returns:
            bool: 如果更新成功，返回 True；否則返回 False。
        """
        query = "UPDATE reports SET analysis_json = ?, status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        log_props = {"report_id": report_id, "new_status": status, "operation": "update_report_analysis"}
        try:
            await self._execute_query(self.reports_db_path, query, (analysis_data, status, report_id), commit=True)
            logger.info(
                f"報告 ID {report_id} 的 AI 分析結果已儲存，狀態更新為 '{status}'。",
                extra={"props": {**log_props, "db_operation_status": "success"}}
            )
            return True
        except Exception as e:
            logger.error(
                f"儲存報告 ID {report_id} 的 AI 分析結果失敗: {e}", exc_info=False,
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def update_report_metadata(self, report_id: int, metadata_update: Dict[str, Any]) -> bool:
        """
        更新指定報告的元數據。
        它會獲取現有的元數據，將其與 `metadata_update` 合併，然後寫回資料庫。

        Args:
            report_id (int): 要更新元數據的報告的 ID。
            metadata_update (Dict[str, Any]): 包含要更新或添加的元數據鍵值對的字典。

        Returns:
            bool: 如果元數據更新成功，返回 True；否則返回 False (例如，報告不存在或資料庫錯誤)。
        """
        log_props = {"report_id": report_id, "operation": "update_report_metadata"}
        current_report = await self.get_report_by_id(report_id) # get_report_by_id logs its own errors
        if not current_report:
            logger.error(f"更新 metadata 失敗：找不到報告 ID {report_id}。", extra={"props": {**log_props, "error": "report_not_found"}})
            return False
        try:
            current_metadata_str = current_report.get("metadata")
            current_metadata = json.loads(current_metadata_str) if current_metadata_str else {}
            current_metadata.update(metadata_update)
            new_metadata_str = json.dumps(current_metadata, ensure_ascii=False)
            query = "UPDATE reports SET metadata = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
            await self._execute_query(self.reports_db_path, query, (new_metadata_str, report_id), commit=True)
            logger.info(f"報告 ID {report_id} 的 metadata 已更新。", extra={"props": {**log_props, "db_operation_status": "success"}})
            return True
        except json.JSONDecodeError as e_json:
            logger.error(f"解析報告 ID {report_id} 的現有 metadata 失敗: {e_json}", exc_info=True, extra={"props": {**log_props, "error": "json_decode_error", "error_message": str(e_json)}})
            return False
        except Exception as e: # Catch errors from _execute_query or other issues
            logger.error(
                f"更新報告 ID {report_id} 的 metadata 時發生錯誤: {e}", exc_info=False, # _execute_query logs with exc_info=True if it's a db error
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def check_report_exists_by_source_path(self, source_path: str) -> bool:
        """
        根據來源路徑檢查報告是否已存在於資料庫中。
        用於防止重複處理相同的報告。

        Args:
            source_path (str): 要檢查的報告的來源路徑。

        Returns:
            bool: 如果具有相同 source_path 的報告已存在，則返回 True；否則返回 False。
                  如果在檢查過程中發生錯誤，也可能返回 False (並記錄錯誤)。
        """
        query = "SELECT 1 FROM reports WHERE source_path = ? LIMIT 1"
        try:
            result = await self._execute_query(self.reports_db_path, query, (source_path,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"檢查報告是否存在 (source_path: {source_path}) 時失敗: {e}", exc_info=True, extra={"props": {"source_path": source_path, "operation": "check_report_exists", "error": str(e)}})
            return False # Or re-raise depending on desired strictness

    async def insert_prompt_template(self, name: str, template_text: str, category: Optional[str] = None) -> Optional[int]:
        """
        將新的提示詞範本插入到 'prompt_templates' 資料庫。

        Args:
            name (str): 提示詞範本的唯一名稱。
            template_text (str): 提示詞範本的內容。
            category (Optional[str], optional): 提示詞範本的類別。預設為 None。

        Returns:
            Optional[int]: 如果插入成功，返回新提示詞範本的 ID；否則返回 None。
        """
        query = "INSERT INTO prompt_templates (name, template_text, category) VALUES (?, ?, ?)"
        log_props = {"prompt_name": name, "category": category, "operation": "insert_prompt_template"}
        try:
            last_row_id = await self._execute_query(self.prompts_db_path, query, (name, template_text, category), commit=True)
            logger.info(
                f"新提示詞範本 '{name}' 已插入到 prompts 資料庫，ID: {last_row_id}",
                extra={"props": {**log_props, "prompt_id": last_row_id, "db_operation_status": "success"}}
            )
            return last_row_id
        except Exception as e:
            logger.error(
                f"插入提示詞範本 '{name}' 失敗: {e}", exc_info=False,
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return None

    # Methods get_prompt_template_by_name and get_all_prompt_templates are read-only,
    # less critical for adding 'extra' unless specific errors in them need richer context.
    # For now, _execute_query will catch and log their query errors with context.

    # ... (rest of the DAL, including prompt methods and __main__ test block, remains largely unchanged for logging 'extra') ...
    # ... (get_prompt_template_by_name and get_all_prompt_templates will benefit from _execute_query's error logging) ...
    async def get_prompt_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根據名稱從資料庫中檢索單個提示詞範本。

        Args:
            name (str): 要檢索的提示詞範本的名稱。

        Returns:
            Optional[Dict[str, Any]]: 如果找到範本，則返回包含範本資料的字典；否則返回 None。
                                     字典鍵對應於 'prompt_templates' 表的欄位名。
        """
        query = "SELECT id, name, template_text, category, created_at, updated_at FROM prompt_templates WHERE name = ?"
        try:
            async with aiosqlite.connect(self.prompts_db_path) as db:
                db.row_factory = aiosqlite.Row # 結果可以通過欄位名訪問
                cursor = await db.execute(query, (name,))
                row = await cursor.fetchone()
                await cursor.close()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"查詢提示詞範本 '{name}' 失敗: {e}", exc_info=True, extra={"props": {"prompt_name": name, "operation": "get_prompt_by_name", "error": str(e)}})
            return None

    async def get_all_prompt_templates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        從資料庫中檢索所有提示詞範本的列表，支持分頁。

        Args:
            limit (int, optional): 要檢索的最大範本數量。預設為 100。
            offset (int, optional): 開始檢索的偏移量 (用於分頁)。預設為 0。

        Returns:
            List[Dict[str, Any]]: 包含提示詞範本資料字典的列表。
                                  如果沒有找到範本或發生錯誤，則返回空列表。
                                  列表中的每個字典包含 'id', 'name', 'category', 'updated_at' 欄位。
        """
        query = "SELECT id, name, category, updated_at FROM prompt_templates ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        try:
            async with aiosqlite.connect(self.prompts_db_path) as db:
                db.row_factory = aiosqlite.Row # 結果可以通過欄位名訪問
                cursor = await db.execute(query, (limit, offset))
                rows = await cursor.fetchall()
                await cursor.close()
            if rows:
                return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(f"查詢所有提示詞範本失敗: {e}", exc_info=True, extra={"props": {"limit": limit, "offset": offset, "operation": "get_all_prompts", "error": str(e)}})
            return []

# __main__ block for testing DAL (copied, no changes needed for 'extra' here as it's for testing)
# 注意: get_all_reports 方法是在 __main__ 塊中使用的，但在 DataAccessLayer 類定義中並未明確提供。
# 如果這是一個預期功能，它應該被添加到類定義中。
# 假設它是測試腳本中的一個輔助函數或是一個遺漏的方法。
if __name__ == '__main__':
    import asyncio
    # ... (rest of __main__ block) ...
    # 下面添加一個 get_all_reports 的示例實現，因為它在測試代碼中被調用
    # 但未在 DataAccessLayer 類中定義。為了使測試代碼完整，這裡模擬一個。
    # 實際應用中，應將此方法正式添加到 DataAccessLayer 類中。

    async def get_all_reports_for_testing(dal_instance, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        (僅為測試目的的輔助函數)
        從資料庫檢索報告列表，支持分頁。
        在實際應用中，此方法應為 DataAccessLayer 類的一部分。
        """
        query = "SELECT id, original_filename, status, processed_at, source_path FROM reports ORDER BY processed_at DESC LIMIT ? OFFSET ?"
        try:
            async with aiosqlite.connect(dal_instance.reports_db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, (limit, offset))
                rows = await cursor.fetchall()
                await cursor.close()
                return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"測試中查詢所有報告失敗: {e}", exc_info=True)
            return []

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    test_reports_db = os.path.join(data_dir, 'test_reports.sqlite')
    test_prompts_db = os.path.join(data_dir, 'test_prompts.sqlite')
    if os.path.exists(test_reports_db): os.remove(test_reports_db)
    if os.path.exists(test_prompts_db): os.remove(test_prompts_db)
    async def main():
        dal = DataAccessLayer(reports_db_path=test_reports_db, prompts_db_path=test_prompts_db)
        logger.info("---- 開始 DataAccessLayer 功能測試 (包含 analysis_json) ----")
        await dal.initialize_databases()
        logger.info("\n---- 測試「報告」相關功能 (包含 analysis_json) ----")
        report_id1 = await dal.insert_report_data("公司週報_2025_第23週.docx", "這是第一份提交的公司內部週報內容。", "/drive/wolf_in/公司週報_2025_第23週.docx", {"author": "王明", "version": "1.0"}, status="內容已解析")
        report_id2 = await dal.insert_report_data("產品月度總結報告.pdf", "這是產品月度總結報告的原始文字。", "/drive/wolf_in/產品月度總結報告.pdf", {"department": "產品部"}, status="內容已解析")
        if report_id1:
            retrieved_report1_before_analysis = await dal.get_report_by_id(report_id1)
            logger.info(f"獲取報告 ID {report_id1} (分析前): {retrieved_report1_before_analysis}")
            analysis_content_1 = {"主要發現": "本週業績良好", "潛在風險": "市場競爭加劇", "建議行動": "加大研發投入"}
            await dal.update_report_analysis(report_id1, json.dumps(analysis_content_1, ensure_ascii=False), "分析完成") # ensure_ascii=False 處理中文
            retrieved_report1_after_analysis = await dal.get_report_by_id(report_id1)
            logger.info(f"獲取報告 ID {report_id1} (分析後): {retrieved_report1_after_analysis}")
        if report_id2:
            await dal.update_report_status(report_id2, "處理中", "這是經過 AI 分析和總結後的產品月度總結報告內容。")
            retrieved_report2_before_analysis = await dal.get_report_by_id(report_id2)
            logger.info(f"獲取報告 ID {report_id2} (分析前，狀態更新後): {retrieved_report2_before_analysis}")
            analysis_content_2 = {"錯誤": "AI分析時遇到內部錯誤"}
            await dal.update_report_analysis(report_id2, json.dumps(analysis_content_2, ensure_ascii=False), "分析失敗") # ensure_ascii=False 處理中文
            retrieved_report2_after_analysis = await dal.get_report_by_id(report_id2)
            logger.info(f"獲取報告 ID {report_id2} (分析失敗後): {retrieved_report2_after_analysis}")

        # 使用上面定義的測試輔助函數
        all_reports = await get_all_reports_for_testing(dal, limit=5)
        logger.info(f"資料庫中所有報告 (部分欄位，最多5條): {all_reports}")

        if report_id1 and retrieved_report1_after_analysis:
            analysis_json_from_db = retrieved_report1_after_analysis.get('analysis_json')
            if analysis_json_from_db:
                analysis_data_from_db = json.loads(analysis_json_from_db)
                logger.info(f"報告 ID {report_id1} 從資料庫解析出的 analysis_data: {analysis_data_from_db}")
                if analysis_data_from_db.get("主要發現") != "本週業績良好": logger.error(f"錯誤：報告 ID {report_id1} 的分析結果與預期不符！")
            else: logger.error(f"錯誤：報告 ID {report_id1} 的 analysis_json 為空！")
        logger.info("\n---- 測試「提示詞範本」相關功能 (無變動) ----")
        prompt_id_test = await dal.insert_prompt_template("測試提示","測試內容")
        logger.info(f"已插入測試提示ID: {prompt_id_test}")
        logger.info(f"\n測試完畢。測試用的資料庫檔案位於目錄: {data_dir}")
    if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
