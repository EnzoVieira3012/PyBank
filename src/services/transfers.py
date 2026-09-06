from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AccountNotFoundError, BusinessError
from src.models.account import Account
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.enums import TransactionType


async def transferir(
    session: AsyncSession,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
    amount: Decimal,
    user: User,
) -> Transaction:
    """Transferencia atomica: lock das duas contas em ordem fixa (ORDER BY id),
    debito + credito + 2 Transaction em um unico commit. Qualquer erro -> rollback
    total no get_session, nenhum lado muda."""
    if from_account_id == to_account_id:
        raise BusinessError("transfer different accounts")

    # Lock unico: SELECT FOR UPDATE com ORDER BY id — transfers cruzadas
    # (A->B e B->A) serializam na mesma ordem, deadlock impossivel.
    accounts = (
        await session.scalars(
            select(Account)
            .where(Account.id.in_([from_account_id, to_account_id]))
            .order_by(Account.id)
            .with_for_update()
        )
    ).all()

    origem = next((a for a in accounts if a.id == from_account_id), None)
    if origem is None or origem.user_id != user.id:
        raise AccountNotFoundError()

    destino = next((a for a in accounts if a.id == to_account_id), None)
    if destino is None:
        raise AccountNotFoundError()

    if origem.balance < amount:
        raise BusinessError("insufficient balance")

    origem.balance -= amount
    destino.balance += amount
    tx_origem = Transaction(
        account_id=origem.id,
        type=TransactionType.TRANSFER,
        amount=amount,
        counterpart_account_id=destino.id,
    )
    tx_destino = Transaction(
        account_id=destino.id,
        type=TransactionType.TRANSFER,
        amount=amount,
        counterpart_account_id=origem.id,
    )
    session.add_all([tx_origem, tx_destino])
    await session.flush()
    await session.refresh(tx_origem)
    return tx_origem
