from wsj.db.base import Filters, Store


def make_store(settings) -> Store:
    """설정에 맞는 Store 구현을 돌려준다. 수집기는 이 함수 밖의 구현을 모른다."""
    if settings.wsj_store == "sqlite":
        from wsj.db.sqlite import SqliteStore

        return SqliteStore(settings.wsj_sqlite_path)
    settings.require_supabase()
    from wsj.db.postgrest import PostgrestStore

    return PostgrestStore(settings.supabase_url, settings.supabase_secret_key)


__all__ = ["Filters", "Store", "make_store"]
