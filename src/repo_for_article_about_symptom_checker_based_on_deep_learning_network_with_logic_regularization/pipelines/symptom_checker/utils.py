import torch
import torch.nn.functional as F

def one_hot_diff(logits: torch.FloatTensor, mode: str, threshold: float = 0.5) -> torch.FloatTensor:

    assert mode in ['sigmoid', 'softmax'], 'Поддерживается бинаризация только сигмоиды или софтмакса'
    assert logits.ndim == 2, 'Предпологается вход размером bacth_size * n_classes'

    if mode == 'sigmoid':
        probs = torch.sigmoid(logits)
        oh_mask = torch.where(probs >= threshold, 1, 0).to(probs.device)
    elif mode == 'softmax':
        probs = torch.softmax(logits, dim=1)
        oh_mask = F.one_hot(probs.argmax(dim=1), num_classes=probs.shape[1])

    # binnarization trick (like in Gumbel-Softmax)
    oh_diff = oh_mask - probs.detach() + probs

    return oh_diff


def gumbel_softmax(logits: torch.Tensor, tau: float = 1, hard: bool = False, eps: float = 1e-10, dim: int = -1) -> torch.Tensor:
    r"""
    Samples from the Gumbel-Softmax distribution (`Link 1`_  `Link 2`_) and optionally discretizes.

    Args:
      logits: `[..., num_features]` unnormalized log probabilities
      tau: non-negative scalar temperature
      hard: if ``True``, the returned samples will be discretized as one-hot vectors,
            but will be differentiated as if it is the soft sample in autograd
      dim (int): A dimension along which softmax will be computed. Default: -1.

    Returns:
      Sampled tensor of same shape as `logits` from the Gumbel-Softmax distribution.
      If ``hard=True``, the returned samples will be one-hot, otherwise they will
      be probability distributions that sum to 1 across `dim`.

    .. note::
      This function is here for legacy reasons, may be removed from nn.Functional in the future.

    .. note::
      The main trick for `hard` is to do  `y_hard - y_soft.detach() + y_soft`

      It achieves two things:
      - makes the output value exactly one-hot
      (since we add then subtract y_soft value)
      - makes the gradient equal to y_soft gradient
      (since we strip all other gradients)

    Examples::
        >>> logits = torch.randn(20, 32)
        >>> # Sample soft categorical using reparametrization trick:
        >>> F.gumbel_softmax(logits, tau=1, hard=False)
        >>> # Sample hard categorical using "Straight-through" trick:
        >>> F.gumbel_softmax(logits, tau=1, hard=True)

    .. _Link 1:
        https://arxiv.org/abs/1611.00712
    .. _Link 2:
        https://arxiv.org/abs/1611.01144
    """
    #if has_torch_function_unary(logits):
    #    return handle_torch_function(gumbel_softmax, (logits,), logits, tau=tau, hard=hard, eps=eps, dim=dim)
    #if eps != 1e-10:
    #    warnings.warn("`eps` parameter is deprecated and has no effect.")

    gumbels = (
        -torch.empty_like(logits, memory_format=torch.legacy_contiguous_format).exponential_().log()
    )  # ~Gumbel(0,1)
    gumbels = (logits + gumbels) / tau  # ~Gumbel(logits,tau)
    y_soft = gumbels.softmax(dim)

    if hard:
        # Straight through.
        index = y_soft.max(dim, keepdim=True)[1]
        y_hard = torch.zeros_like(logits, memory_format=torch.legacy_contiguous_format).scatter_(dim, index, 1.0)
        ret = y_hard - y_soft.detach() + y_soft
    else:
        # Reparametrization trick.
        ret = y_soft
    return ret