from supervisor.core.circuit_breaker import CircuitBreaker

def test_retry_limit_trips():
    cb = CircuitBreaker(max_retries_per_task=3)
    # Attempt 1
    can_cont, reason = cb.record_attempt(0, False, "fix error 1", "reply 1")
    assert can_cont is True
    # Attempt 2
    can_cont, reason = cb.record_attempt(0, False, "fix error 2", "reply 2")
    assert can_cont is True
    # Attempt 3 (trips)
    can_cont, reason = cb.record_attempt(0, False, "fix error 3", "reply 3")
    assert can_cont is False
    assert "上限" in reason
    assert cb.is_tripped is True

def test_similarity_loop_trips():
    cb = CircuitBreaker(similarity_threshold=0.8)
    # Turn 1
    can_cont, _ = cb.record_attempt(0, False, "Prompt A", "I have finished fixing the bug.")
    assert can_cont is True
    # Turn 2: Worker repeats almost identical text
    can_cont, reason = cb.record_attempt(0, False, "Prompt B", "I have finished fixing the bug.")
    assert can_cont is False
    assert "死循环" in reason
